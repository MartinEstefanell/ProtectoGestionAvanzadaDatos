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
        description="Arma la estructura local del lakehouse en artifacts/lakehouse."
    )
    parser.add_argument("--dataset-dir", default="", help="Directorio dataset")
    parser.add_argument("--analytics-dir", default="", help="Directorio analytics")
    parser.add_argument("--curated-dir", default="", help="Directorio datasets_curados")
    parser.add_argument("--lakehouse-dir", default="", help="Directorio lakehouse")
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

    resolved_analytics_dir = (
        Path(args.analytics_dir).resolve()
        if args.analytics_dir.strip()
        else (project_root / "analytics").resolve()
    )

    resolved_curated_dir = (
        Path(args.curated_dir).resolve()
        if args.curated_dir.strip()
        else (project_root / "datasets_curados").resolve()
    )

    # Fuentes raw
    sp500_source = get_required_path(resolved_dataset_dir / "sp500_2022.csv")
    event_source = get_required_path(resolved_dataset_dir / "events_2022.csv")
    event_audit_source = get_required_path(resolved_dataset_dir / "events_audit_2022.csv")

    # Fuentes analíticas
    dim_date_source = get_required_path(resolved_analytics_dir / "dim_date.csv")
    dim_event_source = get_required_path(resolved_analytics_dir / "dim_event.csv")
    fact_sp500_source = get_required_path(resolved_analytics_dir / "fact_sp500.csv")

    # Fuentes curadas
    sp500_curated_source = get_required_path(resolved_curated_dir / "sp500_2022_curado.csv")
    event_curated_source = get_required_path(resolved_curated_dir / "events_2022_curado.csv")
    event_audit_curated_source = get_required_path(
        resolved_curated_dir / "events_audit_2022_curado.csv"
    )

    # Estructura destino
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

    # Copia raw
    copy_if_needed(sp500_source, raw_sp500_dir / "sp500_2022.csv")
    copy_if_needed(event_source, raw_event_dir / "events_2022.csv")
    copy_if_needed(event_audit_source, raw_event_audit_dir / "events_audit_2022.csv")

    # Copia dimensiones / hechos
    copy_if_needed(dim_date_source, dimensions_dir / "dim_date.csv")
    copy_if_needed(dim_event_source, dimensions_dir / "dim_event.csv")
    copy_if_needed(fact_sp500_source, dimensions_dir / "fact_sp500.csv")

    # Copia curados
    copy_if_needed(sp500_curated_source, curated_sp500_dir / "sp500_2022_curado.csv")
    copy_if_needed(event_curated_source, curated_event_dir / "events_2022_curado.csv")
    copy_if_needed(
        event_audit_curated_source,
        curated_event_audit_dir / "events_audit_2022_curado.csv",
    )

    print(f"Estructura local lista en: {resolved_lakehouse_dir}")
    print("Incluye:")
    print("  raw/sp500/sp500_2022.csv")
    print("  raw/event/events_2022.csv")
    print("  raw/event_audit/events_audit_2022.csv")
    print("  dimensions/dim_date.csv")
    print("  dimensions/dim_event.csv")
    print("  dimensions/fact_sp500.csv")
    print("  curated/sp500_clean/sp500_2022_curado.csv")
    print("  curated/event_clean/events_2022_curado.csv")
    print("  curated/event_audit_clean/events_audit_2022_curado.csv")


if __name__ == "__main__":
    main()