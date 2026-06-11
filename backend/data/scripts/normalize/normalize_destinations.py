"""
Normalize destination/wikidata_destinations.csv
Output:
  data/normalized/destinations.csv          (reference, full schema)
  data/normalized/splink_input/destinations.csv  (Splink-ready)
Schema: destination_id, name, entity_type, parent_id, parent_name, lat, lon
Splink schema adds: unique_id, name_clean
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parents[3]
INPUT  = ROOT / "data/sources/destination/wikidata_destinations.csv"
OUTPUT = ROOT / "data/normalized/destinations.csv"
OUTPUT_SPLINK = ROOT / "data/normalized/splink_input/destinations.csv"

def clean_name(s: pd.Series) -> pd.Series:
    return (
        s.str.strip()
         .str.lower()
         .str.replace(r"[^\w\s'\-]", "", regex=True)
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )


ENTITY_TYPE_MAP = {
    "country":                  "Country",
    "city":                     "City",
    "big city":                 "City",
    "city in the united states":"City",
    "village":                  "City",
    "town":                     "City",
    "municipality":             "City",
    "region":                   "Region",
    "island":                   "Region",
    "archipelago":              "Region",
    "territory":                "Region",
    "province":                 "Province",
    "state":                    "Province",
    "prefecture":               "Province",
    "district":                 "District",
    "borough":                  "District",
    "county":                   "District",
    "commune":                  "District",
    "neighborhood":             "Neighborhood",
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

    df["name"] = df["name"].str.strip()
    df = df[["destination_id", "name", "entity_type", "parent_id", "parent_name", "lat", "lon"]]
    df = df.drop_duplicates(subset=["destination_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"destinations: {len(df)} rows → {OUTPUT}")

    # Splink-ready version
    sp = df.copy()
    sp.insert(0, "unique_id", "dest_" + sp["destination_id"])
    sp.insert(2, "name_clean", clean_name(sp["name"]))
    sp = sp[sp["name_clean"].notna() & (sp["name_clean"] != "")]
    OUTPUT_SPLINK.parent.mkdir(parents=True, exist_ok=True)
    sp.to_csv(OUTPUT_SPLINK, index=False)
    print(f"destinations (splink): {len(sp)} rows → {OUTPUT_SPLINK}")


if __name__ == "__main__":
    run()
