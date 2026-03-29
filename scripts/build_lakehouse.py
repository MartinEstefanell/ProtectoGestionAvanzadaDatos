from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_required_path(path_value: str | Path) -> Path:
    path = Path(path_value).resolve()
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo requerido: {path}")
    return path


def ensure_directory(path_value: str | Path) -> Path:
    path = Path(path_value).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_if_needed(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arma la estructura local del lakehouse y copia los archivos base."
    )
    parser.add_argument("--dataset-dir", default="", help="Directorio dataset")
    parser.add_argument("--lakehouse-dir", default="", help="Directorio lakehouse")
    parser.add_argument("--dim-date-file", default="", help="Ruta del dim_date.csv")
    args = parser.parse_args()

    project_root = get_project_root()

    resolved_lakehouse_dir = (
        Path(args.lakehouse_dir).resolve()
        if args.lakehouse_dir.strip()
        else (project_root / "artifacts" / "lakehouse").resolve()
    )

    resolved_dataset_dir = (
        Path(args.dataset_dir).resolve()
        if args.dataset_dir.strip()
        else (project_root / "dataset").resolve()
    )

    resolved_dim_date_file = (
        Path(args.dim_date_file).resolve()
        if args.dim_date_file.strip()
        else (resolved_lakehouse_dir / "dimensions" / "dim_date.csv").resolve()
    )

    sp500_source = get_required_path(resolved_dataset_dir / "sp500_2022.csv")
    event_source = get_required_path(resolved_dataset_dir / "events_2022.csv")
    event_audit_source = get_required_path(resolved_dataset_dir / "events_audit_2022.csv")
    resolved_dim_date_file = get_required_path(resolved_dim_date_file)

    raw_sp500_dir = resolved_lakehouse_dir / "raw" / "sp500"
    raw_event_dir = resolved_lakehouse_dir / "raw" / "event"
    raw_event_audit_dir = resolved_lakehouse_dir / "raw" / "event_audit"
    dimensions_dir = resolved_lakehouse_dir / "dimensions"
    curated_sp500_dir = resolved_lakehouse_dir / "curated" / "sp500_clean"
    curated_event_dir = resolved_lakehouse_dir / "curated" / "event_clean"
    curated_event_audit_dir = resolved_lakehouse_dir / "curated" / "event_audit_clean"

    ensure_directory(raw_sp500_dir)
    ensure_directory(raw_event_dir)
    ensure_directory(raw_event_audit_dir)
    ensure_directory(dimensions_dir)
    ensure_directory(curated_sp500_dir)
    ensure_directory(curated_event_dir)
    ensure_directory(curated_event_audit_dir)

    copy_if_needed(sp500_source, raw_sp500_dir / "sp500_2022.csv")
    copy_if_needed(event_source, raw_event_dir / "events_2022.csv")
    copy_if_needed(event_audit_source, raw_event_audit_dir / "events_audit_2022.csv")

    target_dim_date = dimensions_dir / "dim_date.csv"
    if resolved_dim_date_file.resolve() != target_dim_date.resolve():
        copy_if_needed(resolved_dim_date_file, target_dim_date)

    print(f"Estructura local lista en: {resolved_lakehouse_dir}")
    print("Incluye:")
    print("  raw/sp500/sp500_2022.csv")
    print("  raw/event/events_2022.csv")
    print("  raw/event_audit/events_audit_2022.csv")
    print("  dimensions/dim_date.csv")
    print("  curated/sp500_clean/")
    print("  curated/event_clean/")
    print("  curated/event_audit_clean/")


if __name__ == "__main__":
    main()