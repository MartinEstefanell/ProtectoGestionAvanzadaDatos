from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import http.client
import socket
import subprocess
from typing import Any, Dict, Iterable, Tuple


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def parse_body(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="ignore")


def send_request(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout: int = 30,
) -> Tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req_headers = {"Accept": "application/json"}
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, parse_body(body)
    except urllib.error.HTTPError as exc:
        return exc.code, parse_body(exc.read())
    except (
        urllib.error.URLError,
        http.client.RemoteDisconnected,
        ConnectionResetError,
        ConnectionAbortedError,
        socket.timeout,
        socket.error,
    ) as exc:
        return -1, f"{exc}"


def wait_for_dremio(base_url: str, timeout: int = 600) -> None:
    status_url = f"{base_url}/apiv2/server_status"
    ui_url = f"{base_url}/"
    start = time.time()
    while time.time() - start < timeout:
        try:
            status_code, body = send_request("GET", status_url)
            if status_code == 200 and isinstance(body, dict) and body.get("status") in {"OK", "RUNNING"}:
                return
            if status_code in {301, 302, 303, 307, 308, 401, 403, 404}:
                return

            ui_code, _ = send_request("GET", ui_url)
            if ui_code in {200, 301, 302, 303, 307, 308, 401, 403}:
                return

            elapsed = int(time.time() - start)
            print(f"Dremio aun no listo ({status_code}). Llevamos {elapsed}s, reintento en 5s.")
        except Exception as exc:
            elapsed = int(time.time() - start)
            print(f"Dremio aun no listo (error {exc}). Llevamos {elapsed}s, reintento en 5s.")
        time.sleep(5)

    raise TimeoutError(f"Dremio no estuvo listo en {timeout} segundos")


def ensure_first_user(base_url: str, user: str, password: str, email: str, timeout: int = 120) -> None:
    url = f"{base_url}/apiv2/bootstrap/firstuser"
    payload = {
        "userName": user,
        "firstName": "Admin",
        "lastName": "User",
        "email": email,
        "createdAt": int(time.time() * 1000),
        "password": password,
    }
    headers = {"Authorization": "_dremionull"}
    start = time.time()

    def body_text(body: Any) -> str:
        if isinstance(body, (dict, list)):
            try:
                return json.dumps(body)
            except Exception:
                return str(body)
        return str(body)

    def is_already_initialized(status_code: int, body: Any) -> bool:
        text = body_text(body).lower()
        markers = ["already", "exists", "initialized", "initialised", "disabled", "created"]
        return status_code in {400, 405, 409} and any(m in text for m in markers)

    while time.time() - start < timeout:
        status_code, body = send_request("PUT", url, payload, headers=headers)
        text = body_text(body)
        if status_code in {200, 201}:
            print(f"firstuser OK (HTTP {status_code}).")
            return
        if is_already_initialized(status_code, body):
            print(f"firstuser indica ya inicializado (HTTP {status_code}): {text[:200]}")
            return
        elapsed = int(time.time() - start)
        print(f"firstuser aun no aceptado (HTTP {status_code}): {text[:200]} | llevamos {elapsed}s, reintento en 5s.")
        time.sleep(5)

    raise TimeoutError("No se pudo crear/confirmar el usuario admin antes del timeout.")


def login_with_retry(
    base_url: str,
    user: str,
    password: str,
    total_timeout: int = 60,
    interval: int = 5,
    verbose: bool = False,
) -> str:
    start = time.time()
    last_error: str | None = None
    while time.time() - start < total_timeout:
        try:
            return login(base_url, user, password)
        except RuntimeError as exc:
            last_error = str(exc)
            if verbose:
                elapsed = int(time.time() - start)
                print(f"Login aun falla ({last_error}) tras {elapsed}s, reintento en {interval}s.")
            time.sleep(interval)
    raise RuntimeError(f"Login no disponible despues de {total_timeout}s. Ultimo error: {last_error}")


def login(base_url: str, user: str, password: str) -> str:
    url = f"{base_url}/apiv2/login"
    status_code, body = send_request("POST", url, {"userName": user, "password": password})
    if status_code != 200 or not isinstance(body, dict) or "token" not in body:
        raise RuntimeError(f"No se pudo autenticar en Dremio (HTTP {status_code}). Respuesta: {body}")
    return str(body["token"])


def fetch_source(base_url: str, token: str, source_name: str) -> Tuple[int, Any]:
    headers = {"Authorization": f"_dremio{token}"}
    url = f"{base_url}/api/v3/catalog/{source_name}"
    status, body = send_request("GET", url, headers=headers)
    if status != 404:
        return status, body

    list_status, list_body = send_request("GET", f"{base_url}/api/v3/catalog?type=source", headers=headers)
    if list_status != 200 or not isinstance(list_body, dict):
        return list_status, list_body

    for entry in list_body.get("data", []):
        path = entry.get("path", [])
        if path and path[0] == source_name:
            src_id = entry.get("id")
            return send_request("GET", f"{base_url}/api/v3/catalog/{src_id}", headers=headers)

    return 404, {"errorMessage": f"source {source_name} not found"}


def fetch_source_with_retry(
    base_url: str,
    token: str,
    source_name: str,
    attempts: int = 30,
    delay: float = 1.0,
) -> Tuple[int, Any]:
    status, body = 404, None
    for _ in range(attempts):
        status, body = fetch_source(base_url, token, source_name)
        if status != 404:
            return status, body
        time.sleep(delay)
    return status, body


def delete_source(base_url: str, token: str, source_name: str, tag: str | None = None) -> Tuple[int, Any]:
    url = f"{base_url}/api/v3/source/{source_name}"
    if tag:
        url = f"{url}?tag={tag}"
    return send_request("DELETE", url, headers={"Authorization": f"_dremio{token}"})


def delete_source_fetch_tag(base_url: str, token: str, source_name: str) -> Tuple[int, Any]:
    status, body = fetch_source(base_url, token, source_name)
    if status != 200 or not isinstance(body, dict):
        return status, body
    tag = body.get("tag")
    return delete_source(base_url, token, source_name, tag)


def property_list(minio_endpoint: str) -> Iterable[Dict[str, str]]:
    return [
        {"name": "fs.s3a.endpoint", "value": minio_endpoint},
        {"name": "fs.s3a.path.style.access", "value": "true"},
        {"name": "dremio.s3.compat", "value": "true"},
    ]


def normalize_aws_root_path(warehouse_path: str) -> str:
    if warehouse_path.startswith("s3a://"):
        warehouse_path = warehouse_path[len("s3a://"):]
    if not warehouse_path.startswith("/"):
        warehouse_path = "/" + warehouse_path
    return warehouse_path


def encode_access_secret(secret: str) -> str:
    return secret


def candidate_configs(
    nessie_uri: str,
    branch: str,
    access_key: str,
    secret_key: str,
    root_path: str,
    warehouse_path: str,
    minio_endpoint: str,
) -> Iterable[Dict[str, Any]]:
    cfg = {
        "nessieEndpoint": nessie_uri,
        "nessieAuthType": "NONE",
        "credentialType": "ACCESS_KEY",
        "awsAccessKey": access_key,
        "awsAccessSecret": encode_access_secret(secret_key),
        "awsRootPath": normalize_aws_root_path(warehouse_path),
        "secure": False,
        "propertyList": list(property_list(minio_endpoint)),
        "asyncEnabled": True,
        "isCachingEnabled": True,
        "maxCacheSpacePct": 100,
        "defaultCtasFormat": "ICEBERG",
        "storageProvider": "AWS",
        "azureAuthenticationType": "ACCESS_KEY",
        "googleAuthenticationType": "SERVICE_ACCOUNT_KEYS",
    }
    yield cfg


def create_source(
    base_url: str,
    token: str,
    source_name: str,
    cfgs: Iterable[Dict[str, Any]],
    verbose: bool = False,
) -> None:
    url = f"{base_url}/api/v3/catalog"
    headers = {"Authorization": f"_dremio{token}"}
    last_error: str | None = None
    cfg_list = list(cfgs)

    for idx, cfg in enumerate(cfg_list, start=1):
        payload = {
            "entityType": "source",
            "name": source_name,
            "type": "NESSIE",
            "config": cfg,
            "skipValidation": True,
        }
        if verbose:
            print(f"Intento crear fuente variante {idx}/{len(cfg_list)}: {json.dumps(cfg, indent=2)}")

        status_code, body = send_request("POST", url, payload, headers=headers)

        if status_code == 409:
            delete_source_fetch_tag(base_url, token, source_name)
            status_code, body = send_request("POST", url, payload, headers=headers)

        if verbose:
            print(f"  -> resultado HTTP {status_code}, body: {body}")

        if status_code in {200, 201, 409}:
            return

        last_error = f"HTTP {status_code}: {body}"

    raise RuntimeError(f"No se pudo crear la fuente Nessie en Dremio. {last_error}")


def update_source(base_url: str, token: str, existing: Dict[str, Any], cfgs: Iterable[Dict[str, Any]]) -> None:
    url = f"{base_url}/api/v3/source/{existing['name']}"
    headers = {"Authorization": f"_dremio{token}"}
    last_error: str | None = None

    for cfg in cfgs:
        payload = {
            "id": existing.get("id"),
            "name": existing["name"],
            "type": existing.get("type", "NESSIE"),
            "config": cfg,
            "tag": existing.get("tag"),
            "skipValidation": True,
        }
        status_code, body = send_request("PUT", url, payload, headers=headers)
        if status_code in {200, 201}:
            return
        last_error = f"HTTP {status_code}: {body}"

    raise RuntimeError(f"No se pudo actualizar la fuente Nessie. {last_error}")


def config_matches(current: Dict[str, Any], desired_cfgs: Iterable[Dict[str, Any]]) -> bool:
    cfg = current.get("config", {})
    for desired in desired_cfgs:
        ok = True
        for key in ["secure", "awsAccessKey", "awsRootPath", "storageProvider", "credentialType"]:
            if cfg.get(key) != desired.get(key):
                ok = False
                break
        if not ok:
            continue

        current_uri = cfg.get("nessieEndpoint")
        desired_uri = desired.get("nessieEndpoint")
        if current_uri != desired_uri:
            continue

        desired_props = {p["name"]: p["value"] for p in desired.get("propertyList", [])}
        current_props = {p["name"]: p["value"] for p in cfg.get("propertyList", [])}
        prop_ok = all(current_props.get(k) == v for k, v in desired_props.items())
        if prop_ok:
            return True

    return False


def bootstrap_minio(verbose: bool = False) -> None:
    print("[INFO] Configurando MinIO en Dremio (auto bootstrap)...")

    try:
        result = subprocess.run(
            [sys.executable, "scripts/bootstrap_minio.py"],
            check=True,
            capture_output=not verbose,
            text=True,
        )

        if verbose and result.stdout:
            print(result.stdout)

        print("[OK] MinIO conectado automaticamente a Dremio")

    except subprocess.CalledProcessError as e:
        print("[ERROR] Fallo bootstrap de MinIO")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        raise RuntimeError("No se pudo ejecutar scripts/bootstrap_minio.py correctamente") from e


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap automatico de Dremio para Nessie + MinIO.")
    parser.add_argument("--host", default=env("DREMIO_HOST", "localhost"), help="Host del coordinador Dremio")
    parser.add_argument("--port", default=env("DREMIO_PORT", "9047"), help="Puerto del coordinador Dremio")
    parser.add_argument("--secure", action="store_true", help="Usar HTTPS para llamar a Dremio")
    parser.add_argument("--admin-user", default=env("DREMIO_ADMIN_USER", "admin"), help="Usuario admin a crear/usar")
    parser.add_argument(
        "--admin-password",
        default=env("DREMIO_ADMIN_PASSWORD", "admin123"),
        help="Password del usuario admin",
    )
    parser.add_argument(
        "--admin-email",
        default=env("DREMIO_ADMIN_EMAIL", "admin@example.com"),
        help="Email para el usuario admin",
    )
    parser.add_argument(
        "--source-name",
        default=env("DREMIO_SOURCE_NAME", "nessie"),
        help="Nombre de la fuente Nessie en Dremio",
    )
    parser.add_argument(
        "--nessie-uri",
        default=env("NESSIE_API_URI", "http://nessie:19120/api/v2"),
        help="Endpoint REST de Nessie",
    )
    parser.add_argument(
        "--nessie-branch",
        default=env("NESSIE_BRANCH", "main"),
        help="Branch por defecto en Nessie",
    )
    parser.add_argument(
        "--warehouse-path",
        default=env("WAREHOUSE_PATH", "s3a://lakehouse/warehouse"),
        help="Ruta warehouse para tablas Iceberg",
    )
    parser.add_argument("--root-path", default=env("NESSIE_ROOT_PATH", "/"), help="Prefijo raiz en el bucket")
    parser.add_argument(
        "--minio-endpoint",
        default=env("MINIO_INTERNAL_ENDPOINT", "minio:9000"),
        help="Endpoint interno S3/MinIO para que Dremio lo use, sin http://",
    )
    parser.add_argument(
        "--access-key",
        default=env("MINIO_ROOT_USER", "admin"),
        help="Access key S3/MinIO para Dremio",
    )
    parser.add_argument(
        "--secret-key",
        default=env("MINIO_ROOT_PASSWORD", "password"),
        help="Secret key S3/MinIO para Dremio",
    )
    parser.add_argument("--force-recreate", action="store_true", help="Forzar recrear/actualizar la fuente Nessie")
    parser.add_argument("--validate-only", action="store_true", help="Solo validar que la fuente existe y coincide")
    parser.add_argument("--verbose", action="store_true", help="Imprimir detalles adicionales de debugging")
    parser.add_argument("--skip-ensure-user", action="store_true", help="No intenta crear usuario admin")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    scheme = "https" if args.secure else "http"
    base_url = f"{scheme}://{args.host}:{args.port}"

    print(f"[1/6] Esperando a que Dremio este listo en {base_url} ...")
    wait_for_dremio(base_url)

    if not args.skip_ensure_user:
        print("[2/6] Asegurando usuario admin ...")
        ensure_first_user(base_url, args.admin_user, args.admin_password, args.admin_email)
    else:
        print("[2/6] Saltando creacion de usuario admin (--skip-ensure-user)")

    print("[3/6] Autenticando ...")
    try:
        token = login(base_url, args.admin_user, args.admin_password)
    except RuntimeError as exc:
        if "No User Available" in str(exc):
            print("No hay usuario admin (login 403). Intentando crear con bootstrap/firstuser ...")
            ensure_first_user(base_url, args.admin_user, args.admin_password, args.admin_email, timeout=120)
            token = login_with_retry(
                base_url, args.admin_user, args.admin_password, total_timeout=60, interval=5, verbose=args.verbose
            )
        else:
            raise

    minio_ep = args.minio_endpoint.strip()
    cfgs = list(
        candidate_configs(
            args.nessie_uri,
            args.nessie_branch,
            args.access_key,
            args.secret_key,
            args.root_path,
            args.warehouse_path,
            minio_ep,
        )
    )

    if args.verbose:
        print("Configuracion deseada (primer candidato):")
        print(json.dumps(cfgs[0], indent=2))

    print(f"[4/6] Creando/validando fuente '{args.source_name}' hacia Nessie + MinIO ...")
    status_code, current = fetch_source(base_url, token, args.source_name)

    if args.force_recreate and status_code == 200:
        if args.verbose:
            print("Se pidio --force-recreate, eliminando fuente existente antes de crear...")
        delete_source_fetch_tag(base_url, token, args.source_name)
        status_code, current = fetch_source(base_url, token, args.source_name)

    if status_code == 404:
        if args.validate_only:
            raise RuntimeError("Fuente no existe y se pidio solo validar (--validate-only).")
        if args.verbose:
            print("No existe, se creara.")
        create_source(base_url, token, args.source_name, cfgs, verbose=args.verbose)
        status_code, current = fetch_source_with_retry(base_url, token, args.source_name, attempts=5, delay=1.0)
    elif status_code == 200:
        if args.verbose:
            print("Fuente encontrada, verificando configuracion ...")
    else:
        raise RuntimeError(f"No se pudo obtener la fuente (HTTP {status_code}): {current}")

    if status_code == 200:
        if args.force_recreate or not config_matches(current, cfgs):
            if args.validate_only:
                raise RuntimeError("Fuente desalineada y se pidio solo validar (--validate-only).")
            print("Configuracion diferente, se actualiza la fuente ...")
            update_source(base_url, token, current, cfgs)
            status_code, current = fetch_source_with_retry(base_url, token, args.source_name, attempts=5, delay=1.0)
            if status_code != 200 or not config_matches(current, cfgs):
                raise RuntimeError("La fuente sigue desalineada despues de actualizar.")
        else:
            print("Fuente ya coincide, no se modifica.")

    if args.verbose:
        print("Configuracion final de la fuente:")
        print(json.dumps(current, indent=2))

    print("[5/6] Validacion final de Nessie ...")
    if config_matches(current, cfgs):
        print("OK: la fuente Nessie esta alineada y lista.")
    else:
        raise RuntimeError("Validacion final fallo: la configuracion no coincide.")

    print("[6/6] Configurando MinIO automaticamente ...")
    bootstrap_minio(verbose=args.verbose)

    print("Bootstrap completo: Dremio + Nessie + MinIO listos.")


if __name__ == "__main__":
    main()