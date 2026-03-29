
from pathlib import Path
import argparse

import pandas as pd


def convertir_csv_a_xlsx(archivo_csv: Path, archivo_xlsx: Path) -> None:
    if not archivo_csv.exists():
        raise FileNotFoundError(f"No se encontro el archivo CSV: {archivo_csv}")

    df = pd.read_csv(archivo_csv)
    df.to_excel(archivo_xlsx, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte un archivo CSV a XLSX (Excel)."
    )
    parser.add_argument(
        "archivo_csv",
        nargs="?",
        default="sp500_2022.csv",
        help="Ruta del archivo CSV de entrada (por defecto: sp500_2022.csv).",
    )
    parser.add_argument(
        "archivo_xlsx",
        nargs="?",
        default=None,
        help="Ruta del archivo XLSX de salida (por defecto: mismo nombre con .xlsx).",
    )

    args = parser.parse_args()

    archivo_csv = Path(args.archivo_csv)
    archivo_xlsx = (
        Path(args.archivo_xlsx)
        if args.archivo_xlsx
        else archivo_csv.with_suffix(".xlsx")
    )

    convertir_csv_a_xlsx(archivo_csv, archivo_xlsx)
    print(f"Convertido: {archivo_csv} -> {archivo_xlsx}")


if __name__ == "__main__":
    main()