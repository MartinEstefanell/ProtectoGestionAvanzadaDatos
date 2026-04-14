import os
import sys
import time
import requests





DREMIO_URL = os.getenv("DREMIO_URL", "http://localhost:9047")
DREMIO_USER = os.getenv("DREMIO_USER", "admin")
DREMIO_PASSWORD = os.getenv("DREMIO_PASSWORD", "admin123")

MINIO_SOURCE_NAME = os.getenv("MINIO_SOURCE_NAME", "minio_files")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lakehouse")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")

TIMEOUT_SECONDS = int(os.getenv("BOOTSTRAP_TIMEOUT_SECONDS", "180"))





def wait_for_dremio():
    deadline = time.time() + TIMEOUT_SECONDS

    while time.time() < deadline:
        try:
            r = requests.get(f"{DREMIO_URL}/", timeout=5)
            if r.status_code in (200, 302):
                print("[OK] Dremio está listo")
                return
        except requests.RequestException:
            pass

        print("[INFO] Esperando Dremio...")
        time.sleep(3)

    raise RuntimeError("Dremio no respondió a tiempo")


def login():
    payload = {
        "userName": DREMIO_USER,
        "password": DREMIO_PASSWORD
    }

    r = requests.post(
        f"{DREMIO_URL}/apiv2/login",
        json=payload,
        timeout=10
    )
    r.raise_for_status()

    token = r.json()["token"]
    print("[OK] Login exitoso en Dremio")
    return token


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def source_exists(token):
    r = requests.get(
        f"{DREMIO_URL}/api/v3/catalog",
        headers=headers(token),
        timeout=10
    )
    r.raise_for_status()

    data = r.json().get("data", [])

    for item in data:
        if item.get("containerType") == "SOURCE":
            if item.get("path", [None])[0] == MINIO_SOURCE_NAME:
                print(f"[OK] Source '{MINIO_SOURCE_NAME}' ya existe")
                return True

    return False


def create_source(token):
    payload = {
        "entityType": "source",
        "type": "S3",
        "name": MINIO_SOURCE_NAME,
        "config": {
            "accessKey": MINIO_ACCESS_KEY,
            "accessSecret": MINIO_SECRET_KEY,
            "secure": False,
            "rootPath": "/",
            "compatibilityMode": True,
            "whitelistedBuckets": [MINIO_BUCKET],
            "credentialType": "ACCESS_KEY",
            "propertyList": [
                {
                    "name": "fs.s3a.endpoint",
                    "value": MINIO_ENDPOINT
                },
                {
                    "name": "fs.s3a.path.style.access",
                    "value": "true"
                }
            ]
        }
    }

    r = requests.post(
        f"{DREMIO_URL}/api/v3/catalog",
        headers=headers(token),
        json=payload,
        timeout=20
    )

    if r.status_code >= 400:
        print("[ERROR] Falló la creación del source")
        print(r.status_code, r.text)
        r.raise_for_status()

    print("[OK] Source MinIO creado correctamente")






def main():
    try:
        wait_for_dremio()
        token = login()

        if not source_exists(token):
            create_source(token)

        print("[DONE] Bootstrap MinIO completo")
        return 0

    except Exception as e:
        print(f"[FATAL] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())