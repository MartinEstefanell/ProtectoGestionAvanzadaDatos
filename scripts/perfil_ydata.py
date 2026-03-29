from pathlib import Path
import argparse

import pandas as pd

try:
    from ydata_profiling import ProfileReport
except ImportError as exc:
    raise SystemExit(
        "No se encontro ydata-profiling. Instala con: pip install ydata-profiling"
    ) from exc


def cargar_datos(ruta_entrada: Path) -> pd.DataFrame:
    extension = ruta_entrada.suffix.lower()

    if extension == ".csv":
        return pd.read_csv(ruta_entrada)

    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(ruta_entrada)

    raise ValueError("Formato no soportado. Usa .csv, .xlsx o .xls")


def generar_reporte(ruta_entrada: Path, ruta_salida_html: Path, titulo: str) -> None:
    if not ruta_entrada.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {ruta_entrada}")

    df = cargar_datos(ruta_entrada)
    reporte = ProfileReport(df, title=titulo, explorative=True)
    reporte.to_file(ruta_salida_html)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un reporte HTML de analisis con ydata-profiling."
    )
    parser.add_argument(
        "archivo_entrada",
        nargs="?",
        default="sp500_2022_date_close.csv",
        help="Archivo de entrada (.csv, .xlsx, .xls).",
    )
    parser.add_argument(
        "archivo_salida",
        nargs="?",
        default=None,
        help="Archivo HTML de salida (por defecto: <entrada>_perfil.html).",
    )
    parser.add_argument(
        "--titulo",
        default="Reporte de Perfilado de Datos",
        help="Titulo del reporte.",
    )

    args = parser.parse_args()

    ruta_entrada = Path(args.archivo_entrada)
    ruta_salida = (
        Path(args.archivo_salida)
        if args.archivo_salida
        else ruta_entrada.with_name(f"{ruta_entrada.stem}_perfil.html")
    )

    generar_reporte(ruta_entrada, ruta_salida, args.titulo)
    print(f"Reporte generado: {ruta_salida}")


if __name__ == "__main__":
    main()