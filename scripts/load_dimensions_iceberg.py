from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests






DREMIO_URL = os.getenv("DREMIO_URL", "http://localhost:9047")
DREMIO_USER = os.getenv("DREMIO_USER", "admin")
DREMIO_PASSWORD = os.getenv("DREMIO_PASSWORD", "admin123")

NESSIE_SOURCE = os.getenv("NESSIE_SOURCE", "nessie")
MINIO_SOURCE = os.getenv("MINIO_SOURCE", "minio_files")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lakehouse")
MINIO_DIMENSIONS_PATH = os.getenv("MINIO_DIMENSIONS_PATH", "dimensions")

LOCAL_DIMENSIONS_DIR = Path(
    os.getenv("LOCAL_DIMENSIONS_DIR", "artifacts/lakehouse/dimensions")
)

JOB_TIMEOUT_SECONDS = int(os.getenv("DREMIO_JOB_TIMEOUT_SECONDS", "180"))






def login() -> str:
    resp = requests.post(
        f"{DREMIO_URL}/apiv2/login",
        json={"userName": DREMIO_USER, "password": DREMIO_PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body["token"]


def headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"_dremio{token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def submit_sql(token: str, sql: str) -> str:
    resp = requests.post(
        f"{DREMIO_URL}/api/v3/sql",
        headers=headers(token),
        json={"sql": sql},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    return body["id"]


def wait_for_job(token: str, job_id: str, timeout_seconds: int = JOB_TIMEOUT_SECONDS) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        resp = requests.get(
            f"{DREMIO_URL}/api/v3/job/{job_id}",
            headers=headers(token),
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        state = body.get("jobState")

        if state in {"COMPLETED", "FAILED", "CANCELED"}:
            return body

        time.sleep(2)

    raise TimeoutError(f"El job {job_id} no terminó dentro de {timeout_seconds}s")


def run_sql(token: str, sql: str) -> None:
    print("\n--- SQL ---")
    print(sql)
    job_id = submit_sql(token, sql)
    result = wait_for_job(token, job_id)

    state = result.get("jobState")
    if state != "COMPLETED":
        raise RuntimeError(
            f"Job falló. Estado={state}\nRespuesta:\n{json.dumps(result, indent=2, ensure_ascii=False)}"
        )

    print(f"[OK] Job completado: {job_id}")






def quote_ident(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def read_csv_headers(csv_path: Path) -> List[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)

    if not header:
        raise ValueError(f"No se pudo leer header de: {csv_path}")

    cleaned = [h.strip() for h in header if h and h.strip()]
    if not cleaned:
        raise ValueError(f"Header vacío o inválido en: {csv_path}")

    return cleaned


def drop_table_sql(table_name: str) -> str:
    return f'DROP TABLE IF EXISTS {quote_ident(NESSIE_SOURCE)}.{quote_ident(table_name)}'


def create_table_sql(table_name: str, columns: List[str]) -> str:
    cols_sql = ",\n  ".join(f"{quote_ident(col)} VARCHAR" for col in columns)

    return f"""
CREATE TABLE {quote_ident(NESSIE_SOURCE)}.{quote_ident(table_name)} (
  {cols_sql}
)
""".strip()


def copy_into_sql(table_name: str, csv_filename: str) -> str:
    source_path = f"@{MINIO_SOURCE}/{MINIO_BUCKET}/{MINIO_DIMENSIONS_PATH}"

    return f"""
COPY INTO {quote_ident(NESSIE_SOURCE)}.{quote_ident(table_name)}
FROM '{source_path}'
FILES ('{csv_filename}')
FILE_FORMAT 'csv'
(EXTRACT_HEADER TRUE)
""".strip()


def count_sql(table_name: str) -> str:
    return f"""
SELECT COUNT(*) AS total_registros
FROM {quote_ident(NESSIE_SOURCE)}.{quote_ident(table_name)}
""".strip()






def process_table(token: str, csv_filename: str, iceberg_table_name: str) -> None:
    local_csv = LOCAL_DIMENSIONS_DIR / csv_filename
    print(f"\n[INFO] Procesando {csv_filename} -> {iceberg_table_name}")

    columns = read_csv_headers(local_csv)
    print(f"[INFO] Columnas detectadas: {columns}")

    run_sql(token, drop_table_sql(iceberg_table_name))
    run_sql(token, create_table_sql(iceberg_table_name, columns))
    run_sql(token, copy_into_sql(iceberg_table_name, csv_filename))
    run_sql(token, count_sql(iceberg_table_name))


def main() -> int:
    try:
        if not LOCAL_DIMENSIONS_DIR.exists():
            raise FileNotFoundError(
                f"No existe el directorio local de dimensiones: {LOCAL_DIMENSIONS_DIR}"
            )

        token = login()
        print("[OK] Login en Dremio exitoso")

        process_table(token, "dim_date.csv", "dim_date_iceberg")
        process_table(token, "dim_event.csv", "dim_event_iceberg")
        process_table(token, "fact_sp500.csv", "fact_sp500_iceberg")

        print("\n[DONE] Tablas Iceberg de dimensions creadas y cargadas correctamente.")
        return 0

    except Exception as e:
        print(f"\n[FATAL] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())