"""
Normalize destination/wikidata_regions.csv
Output: data/normalized/destinations.csv
Schema: destination_id, name, entity_type, parent_id, parent_name, lat, lon
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parents[3]
INPUT = ROOT / "data/sources/destination/wikidata_regions.csv"
OUTPUT = ROOT / "data/normalized/destinations.csv"

ENTITY_TYPE_MAP = {
    "country":      "country",
    "city":         "city",
    "region":       "region",
    "province":     "province",
    "district":     "district",
    "neighborhood": "neighborhood",
    "island":       "region",
    "archipelago":  "region",
    "state":        "province",
    "territory":    "region",
    "municipality": "city",
    "town":         "city",
    "borough":      "district",
    "prefecture":   "province",
    "county":       "district",
    "commune":      "district",
}


def run():
    df = pd.read_csv(INPUT, dtype=str)

    df = df.rename(columns={
        "wikidata_id":         "destination_id",
        "parent_wikidata_id":  "parent_id",
    })

    df["entity_type"] = (
        df["entity_type"].str.lower().str.strip()
        .map(lambda x: ENTITY_TYPE_MAP.get(x, x))
    )

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    df = df[["destination_id", "name", "entity_type", "parent_id", "parent_name", "lat", "lon"]]
    df = df.drop_duplicates(subset=["destination_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"destinations: {len(df)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
