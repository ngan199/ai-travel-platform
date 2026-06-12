"""
Normalize attribute tables: language, currency, season, month.
All link to destinations by destination_id (wikidata_id).
Outputs:
  data/normalized/languages.csv
  data/normalized/currencies.csv
  data/normalized/seasons.csv
  data/normalized/months.csv
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parents[3]
SOURCES = ROOT / "data/sources"
OUT = ROOT / "data/normalized"


def normalize_languages():
    df = pd.read_csv(SOURCES / "language/rest_countries.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["is_official_language"] = df["is_official_language"].str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )
    df = df[["destination_id", "destination_name", "language_name", "is_official_language"]]
    df = df.drop_duplicates()
    out = OUT / "languages.csv"
    df.to_csv(out, index=False)
    print(f"languages  : {len(df)} rows → {out}")


def normalize_currencies():
    df = pd.read_csv(SOURCES / "currency/rest_countries.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df = df[["destination_id", "destination_name", "currency_code", "currency_name"]]
    df = df.drop_duplicates()
    out = OUT / "currencies.csv"
    df.to_csv(out, index=False)
    print(f"currencies : {len(df)} rows → {out}")


def normalize_seasons():
    df = pd.read_csv(SOURCES / "season/from_climate.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["avg_temp_celsius"] = pd.to_numeric(df["avg_temp_celsius"], errors="coerce")
    df["avg_rainfall_mm"] = pd.to_numeric(df["avg_rainfall_mm"], errors="coerce")
    df = df[["destination_id", "destination_name", "season_type",
             "month_numbers", "avg_temp_celsius", "avg_rainfall_mm"]]
    df = df.drop_duplicates(subset=["destination_id", "season_type"])

    # Derive climate-based season types from temperature/rainfall thresholds
    derived_rows = []
    for climate_type, mask in [
        ("hot",  df["avg_temp_celsius"] > 28),
        ("cool", df["avg_temp_celsius"] < 15),
        ("dry",  df["avg_rainfall_mm"]  < 50),
    ]:
        subset = df[mask].copy()
        subset["season_type"] = climate_type
        derived_rows.append(subset)

    if derived_rows:
        derived = pd.concat(derived_rows, ignore_index=True)
        df = pd.concat([df, derived], ignore_index=True)
        df = df.drop_duplicates(subset=["destination_id", "season_type"])

    out = OUT / "seasons.csv"
    df.to_csv(out, index=False)
    print(f"seasons    : {len(df)} rows → {out}")


def normalize_months():
    df = pd.read_csv(SOURCES / "season/month_weather.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["month_number"] = pd.to_numeric(df["month_number"], errors="coerce").astype("Int64")
    for col in ("avg_temp_celsius", "avg_rainfall_mm", "avg_humidity"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["destination_id", "destination_name", "month_number",
             "month_name", "avg_temp_celsius", "avg_rainfall_mm", "avg_humidity"]]
    df = df.drop_duplicates(subset=["destination_id", "month_number"])
    out = OUT / "months.csv"
    df.to_csv(out, index=False)
    print(f"months     : {len(df)} rows → {out}")


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    normalize_languages()
    normalize_currencies()
    normalize_seasons()
    normalize_months()


if __name__ == "__main__":
    run()
