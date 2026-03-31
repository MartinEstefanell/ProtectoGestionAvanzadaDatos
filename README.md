# Lakehouse reproducible (MinIO + Nessie + Dremio)

## Servicios que se levantan
- MinIO (S3 compatible) en `localhost:9000` (console `9001`)
- PostgreSQL para Nessie
- Nessie catalog en `localhost:19120`
- Dremio OSS en `localhost:9047`

## Prerrequisitos
- Docker + Docker Compose
- Python 3.10+ y `pip`

Instala dependencias de los scripts:
```bash
python -m pip install -r requirements.txt
```

## Flujo en un solo comando
```bash
python scripts/bootstrap_stack.py
```
Hace:
1) `docker compose up -d`
2) Construye `artifacts/lakehouse` con `build_lakehouse.py`
3) Sube el lakehouse al bucket MinIO `lakehouse`
4) Espera Dremio, crea el usuario admin (si falta) y define/valida la fuente Nessie apuntando a MinIO.
5) Valida que la fuente quede alineada (idempotente).

Flags utiles:
- `--skip-compose` si ya levantaste los contenedores
- `--wait-nessie` para esperar explicitamente a Nessie antes del bootstrap de Dremio
- `--validate-only` para solo validar la fuente (falla si no existe o si difiere)

## Comandos paso a paso (si prefieres manual)
```bash
docker compose up -d
python scripts/build_lakehouse.py
python scripts/upload_to_minio.py --endpoint localhost:9000 --bucket-name lakehouse --access-key admin --secret-key password
python scripts/bootstrap_dremio.py --host localhost --port 9047 --minio-endpoint http://minio:9000 --warehouse-path s3a://lakehouse/warehouse
# Solo validar (sin recrear si falta): agregar --validate-only
# Forzar recrear fuente: agregar --force-recreate
```

## Variables utiles (opcionales, .env)
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_REGION`
- `NESSIE_DB_USER`, `NESSIE_DB_PASSWORD`, `NESSIE_DB_NAME`
- `DREMIO_ADMIN_USER`, `DREMIO_ADMIN_PASSWORD`, `DREMIO_ADMIN_EMAIL`
- `WAREHOUSE_PATH` (ruta donde Dremio escribira Iceberg)
- `MINIO_ENDPOINT` y `MINIO_INTERNAL_ENDPOINT` (externo vs. nombre de servicio docker)

## Siguiente paso
Con el stack arriba y la fuente `nessie` creada, ya puedes ejecutar en Dremio (SQL Runner):
```sql
USE nessie.main;
-- crear tablas Iceberg aqui
```
