from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

CURATED_DIR = BASE_DIR / "datasets_curados"
OUTPUT_DIR = BASE_DIR / "analytics"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# 1. DIM_DATE
# -----------------------------
def build_dim_date():
    sp500_path = CURATED_DIR / "sp500_2022_curado.csv"
    df = pd.read_csv(sp500_path)

    df["date"] = pd.to_datetime(df["date"])

    dim_date = pd.DataFrame()
    dim_date["full_date"] = df["date"].drop_duplicates().sort_values()

    dim_date["date_id"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["day"] = dim_date["full_date"].dt.day
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["year"] = dim_date["full_date"].dt.year
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["day_of_week"] = dim_date["full_date"].dt.day_name()
    dim_date["is_weekend"] = dim_date["day_of_week"].isin(["Saturday", "Sunday"])

    dim_date = dim_date[
        [
            "date_id",
            "full_date",
            "day",
            "month",
            "year",
            "quarter",
            "day_of_week",
            "is_weekend",
        ]
    ]

    dim_date = dim_date.sort_values("full_date").reset_index(drop=True)

    output_path = OUTPUT_DIR / "dim_date.csv"
    dim_date.to_csv(output_path, index=False)

    print(f"OK - dim_date generado en {output_path}")


# -----------------------------
# 2. FACT_SP500
# -----------------------------
def build_fact_sp500():
    sp500_path = CURATED_DIR / "sp500_2022_curado.csv"
    df = pd.read_csv(sp500_path)

    df["date"] = pd.to_datetime(df["date"])
    df["date_id"] = df["date"].dt.strftime("%Y%m%d").astype(int)

    fact = df[
        ["date_id", "open", "high", "low", "close", "volume"]
    ].copy()

    fact = fact.sort_values("date_id").reset_index(drop=True)

    output_path = OUTPUT_DIR / "fact_sp500.csv"
    fact.to_csv(output_path, index=False)

    print(f"OK - fact_sp500 generado en {output_path}")


# -----------------------------
# 3. DIM_EVENT
# -----------------------------
def build_dim_event():
    events_path = CURATED_DIR / "events_2022_curado.csv"
    df = pd.read_csv(events_path)

    df["date"] = pd.to_datetime(df["date"])
    df["date_id"] = df["date"].dt.strftime("%Y%m%d").astype(int)

    dim_event = df[
        ["event_id", "date_id", "event", "category"]
    ].copy()

    dim_event = dim_event.sort_values("date_id").reset_index(drop=True)

    output_path = OUTPUT_DIR / "dim_event.csv"
    dim_event.to_csv(output_path, index=False)

    print(f"OK - dim_event generado en {output_path}")


# -----------------------------
# MAIN
# -----------------------------
def main():
    build_dim_date()
    build_fact_sp500()
    build_dim_event()

    print("\n🔥 Modelo dimensional generado correctamente")


if __name__ == "__main__":
    main()