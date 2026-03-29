from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error
from urllib3.exceptions import MaxRetryError


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_required_path(path_value: str | Path) -> Path:
    path = Path(path_value).resolve()
    if not path.exists():
        raise FileNotFoundError(f"No se encontró la ruta requerida: {path}")
    return path


def create_client(endpoint: str, access_key: str, secret_key: str, secure: bool) -> Minio:
    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def ensure_bucket(client: Minio, bucket_name: str) -> None:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def reset_bucket_if_needed(client: Minio, bucket_name: str, reset_bucket: bool) -> None:
    if not reset_bucket:
        return

    if client.bucket_exists(bucket_name):
        objects = list(client.list_objects(bucket_name, recursive=True))

        if objects:
            delete_objects = [DeleteObject(obj.object_name) for obj in objects]
            delete_errors = client.remove_objects(bucket_name, delete_objects)

            for err in delete_errors:
                raise RuntimeError(f"Error borrando objeto del bucket: {err}")

        client.remove_bucket(bucket_name)

    client.make_bucket(bucket_name)


def upload_directory(client: Minio, bucket_name: str, local_root: Path) -> None:
    for file_path in local_root.rglob("*"):
        if file_path.is_file():
            object_name = file_path.relative_to(local_root).as_posix()
            client.fput_object(bucket_name, object_name, str(file_path))
            print(f"Subido: {object_name}")


def ensure_empty_prefixes(client: Minio, bucket_name: str) -> None:
    empty_objects = [
        "curated/sp500_clean/.keep",
        "curated/event_clean/.keep",
        "curated/event_audit_clean/.keep",
    ]

    for object_name in empty_objects:
        client.put_object(
            bucket_name,
            object_name,
            data=BytesIO(b""),
            length=0,
            content_type="application/octet-stream",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea o actualiza un bucket en MinIO y sincroniza el lakehouse local."
    )
    parser.add_argument("--bucket-name", default="lakehouse")
    parser.add_argument("--lakehouse-dir", default="")
    parser.add_argument("--endpoint", default="localhost:9000")
    parser.add_argument("--access-key", default="admin")
    parser.add_argument("--secret-key", default="password")
    parser.add_argument("--secure", action="store_true", help="Usar HTTPS")
    parser.add_argument("--reset-bucket", action="store_true", help="Borrar y recrear bucket")
    args = parser.parse_args()

    project_root = get_project_root()
    resolved_lakehouse_dir = (
        Path(args.lakehouse_dir).resolve()
        if args.lakehouse_dir.strip()
        else (project_root / "artifacts" / "lakehouse").resolve()
    )

    resolved_lakehouse_dir = get_required_path(resolved_lakehouse_dir)
    get_required_path(resolved_lakehouse_dir / "raw" / "sp500" / "sp500_2022.csv")
    get_required_path(resolved_lakehouse_dir / "raw" / "event" / "events_2022.csv")
    get_required_path(resolved_lakehouse_dir / "raw" / "event_audit" / "events_audit_2022.csv")
    get_required_path(resolved_lakehouse_dir / "dimensions" / "dim_date.csv")

    try:
        client = create_client(
            endpoint=args.endpoint,
            access_key=args.access_key,
            secret_key=args.secret_key,
            secure=args.secure,
        )

        reset_bucket_if_needed(client, args.bucket_name, args.reset_bucket)
        ensure_bucket(client, args.bucket_name)
        upload_directory(client, args.bucket_name, resolved_lakehouse_dir)
        ensure_empty_prefixes(client, args.bucket_name)

        print(f"Bucket creado o actualizado: {args.bucket_name}")
        print(f"Objetos sincronizados desde: {resolved_lakehouse_dir}")
        print("Si quieres borrar objetos viejos del bucket, ejecuta este script con --reset-bucket.")

    except (S3Error, MaxRetryError) as exc:
        raise RuntimeError(f"Error trabajando con MinIO: {exc}") from exc


if __name__ == "__main__":
    main()