from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "dataset"
OUTPUT_DIR = BASE_DIR / "datasets_curados"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def curar_sp500() -> None:
    input_path = INPUT_DIR / "sp500_2022.csv"
    output_path = OUTPUT_DIR / "sp500_2022_curado.csv"

    df = pd.read_csv(input_path)

    # El archivo original viene con:
    # encabezados: Price, Close, High, Low, Open, Volume
    # primera fila de datos: ticker (^GSPC)
    # resto: datos reales
    #
    # Luego de leer con pandas, la fila del ticker queda como la primera fila de datos.
    # Por eso la eliminamos.
    df = df.iloc[1:].copy()

    # Renombrar columnas a una estructura más clara para análisis
    df.columns = ["date", "close", "high", "low", "open", "volume"]

    # Convertir tipos
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    numeric_cols = ["close", "high", "low", "open", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Eliminar filas inválidas
    df = df.dropna(subset=["date"])

    # Ordenar y resetear índice
    df = df.sort_values("date").reset_index(drop=True)

    # Guardar
    df.to_csv(output_path, index=False)
    print(f"OK - sp500 curado guardado en: {output_path}")


def curar_events() -> None:
    input_path = INPUT_DIR / "events_2022.csv"
    output_path = OUTPUT_DIR / "events_2022_curado.csv"

    df = pd.read_csv(input_path)

    df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce").astype("Int64")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["event"] = df["event"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip().str.lower()

    df = df.dropna(subset=["event_id", "date"]).copy()
    df["event_id"] = df["event_id"].astype(int)

    df = df.sort_values(["date", "event_id"]).reset_index(drop=True)

    df.to_csv(output_path, index=False)
    print(f"OK - events curado guardado en: {output_path}")


def curar_events_audit() -> None:
    audit_input_path = INPUT_DIR / "events_audit_2022.csv"
    events_input_path = INPUT_DIR / "events_2022.csv"
    output_path = OUTPUT_DIR / "events_audit_2022_curado.csv"

    audit = pd.read_csv(audit_input_path)
    events = pd.read_csv(events_input_path)

    # Normalización básica
    audit["date"] = pd.to_datetime(audit["date"], errors="coerce")
    audit["event"] = audit["event"].astype(str).str.strip()
    audit["source_event_url"] = audit["source_event_url"].astype(str).str.strip()

    events["event_id"] = pd.to_numeric(events["event_id"], errors="coerce").astype("Int64")
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    events["event"] = events["event"].astype(str).str.strip()
    events["category"] = events["category"].astype(str).str.strip()

    # Validación: en este caso asumimos un solo evento por fecha
    duplicadas = events["date"].duplicated().sum()
    if duplicadas > 0:
        raise ValueError(
            f"Hay {duplicadas} fechas duplicadas en events_2022.csv. "
            "No se puede hacer merge solo por date de forma segura."
        )

    # Merge SOLO por date
    audit = audit.merge(
        events[["event_id", "date"]],
        on="date",
        how="left"
    )

    # Reordenar columnas
    audit = audit[["event_id", "date", "event", "source_event_url"]]

    # Validación final
    unmatched = audit["event_id"].isna().sum()
    if unmatched > 0:
        print(f"ADVERTENCIA - hay {unmatched} registros sin event_id asociado")
    else:
        print("OK - todos los registros de audit quedaron asociados a un event_id")

    audit = audit.dropna(subset=["date"]).copy()
    audit = audit.sort_values(["date", "event_id"], na_position="last").reset_index(drop=True)

    if audit["event_id"].notna().all():
        audit["event_id"] = audit["event_id"].astype(int)

    audit.to_csv(output_path, index=False)
    print(f"OK - events_audit curado guardado en: {output_path}")


def main() -> None:
    curar_sp500()
    curar_events()
    curar_events_audit()
    print("Proceso de curado finalizado.")


if __name__ == "__main__":
    main()