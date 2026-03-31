from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import http.client
import urllib.error
import socket
import urllib.request


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def run_cmd(cmd: list[str], cwd: str | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def run_cmd_with_retry(cmd: list[str], cwd: str | None = None, retries: int = 2, delay: int = 5) -> None:
    attempt = 0
    while True:
        try:
            run_cmd(cmd, cwd)
            return
        except subprocess.CalledProcessError as exc:
            attempt += 1
            if attempt > retries:
                raise
            print(f"Comando fallo (intento {attempt}/{retries+1}): {exc}. Reintentando en {delay}s ...")
            time.sleep(delay)


def wait_http(url: str, timeout: int = 180, interval: int = 5) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status < 400:
                    return
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            http.client.RemoteDisconnected,
            ConnectionResetError,
            ConnectionAbortedError,
            socket.timeout,
            socket.error,
        ) as exc:
            elapsed = int(time.time() - start)
            remaining = int(timeout - (time.time() - start))
            print(f"Aun no listo {url} (llevamos {elapsed}s, reintento en {interval}s). Detalle: {exc}")
        time.sleep(interval)
    raise TimeoutError(f"No hubo respuesta saludable de {url} en {timeout} segundos")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline completo: docker compose up + lakehouse local + carga a MinIO + bootstrap Dremio."
    )
    parser.add_argument("--compose-file", default="docker-compose.yml", help="Ruta al docker-compose a usar")
    parser.add_argument("--skip-compose", action="store_true", help="Omitir docker compose up (ya corriendo)")
    parser.add_argument("--bucket-name", default=env("MINIO_BUCKET", "lakehouse"), help="Bucket en MinIO")
    parser.add_argument(
        "--minio-endpoint", default=env("MINIO_ENDPOINT", "localhost:9000"), help="Endpoint HTTP para subir datos"
    )
    parser.add_argument(
        "--minio-internal-endpoint",
        default=env("MINIO_INTERNAL_ENDPOINT", "http://minio:9000"),
        help="Endpoint que Dremio debe usar (nombre de servicio Docker)",
    )
    parser.add_argument("--minio-access-key", default=env("MINIO_ROOT_USER", "admin"), help="Access key MinIO")
    parser.add_argument("--minio-secret-key", default=env("MINIO_ROOT_PASSWORD", "password"), help="Secret key MinIO")
    parser.add_argument("--dremio-host", default=env("DREMIO_HOST", "localhost"), help="Host del coordinador Dremio")
    parser.add_argument("--dremio-port", default=env("DREMIO_PORT", "9047"), help="Puerto del coordinador Dremio")
    parser.add_argument(
        "--warehouse-path",
        default=env("WAREHOUSE_PATH", "s3a://lakehouse/warehouse"),
        help="Ruta warehouse donde Dremio escribira Iceberg",
    )
    parser.add_argument(
        "--wait-nessie", action="store_true", help="Esperar explicitamente a Nessie antes de bootstrapping Dremio"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Solo validar la fuente en Dremio (no recrea si falta)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if not args.skip_compose:
        run_cmd(["docker", "compose", "-f", args.compose_file, "up", "-d"], cwd=repo_root)
    else:
        print("Skipeando docker compose up (--skip-compose).")

    health_base = args.minio_endpoint
    if not health_base.startswith("http"):
        health_base = f"http://{health_base}"
    wait_http(f"{health_base}/minio/health/live")

    if args.wait_nessie:
        wait_http("http://localhost:19120/api/v2/trees")

    run_cmd_with_retry([sys.executable, "scripts/build_lakehouse.py"], cwd=repo_root)

    run_cmd_with_retry(
        [
            sys.executable,
            "scripts/upload_to_minio.py",
            "--endpoint",
            args.minio_endpoint,
            "--bucket-name",
            args.bucket_name,
            "--access-key",
            args.minio_access_key,
            "--secret-key",
            args.minio_secret_key,
        ],
        cwd=repo_root,
    )

    bootstrap_cmd = [
        sys.executable,
        "scripts/bootstrap_dremio.py",
        "--host",
        args.dremio_host,
        "--port",
        args.dremio_port,
        "--minio-endpoint",
        args.minio_internal_endpoint,
        "--warehouse-path",
        args.warehouse_path,
    ]

    if args.validate_only:
        bootstrap_cmd.append("--validate-only")

    run_cmd_with_retry(bootstrap_cmd, cwd=repo_root)

    print("Stack listo. Revisa Dremio en http://localhost:9047 y deberias ver la fuente 'nessie'.")


if __name__ == "__main__":
    main()
