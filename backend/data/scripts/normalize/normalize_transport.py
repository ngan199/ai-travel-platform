"""
Normalize transport/osm_hubs.csv into Splink input table.
Output: data/normalized/splink_input/transport_hubs.csv
Schema: record_id, name, entity_type, lat, lon, iata_code, source, source_id, destination_id, destination_name
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).parents[3]
INPUT = ROOT / "data/sources/transport/osm_hubs.csv"
OUTPUT = ROOT / "data/normalized/splink_input/transport_hubs.csv"

def clean_name(s: pd.Series) -> pd.Series:
    return (
        s.str.strip()
         .str.lower()
         .str.replace(r"[^\w\s'\-]", "", regex=True)
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )


HUB_TYPE_MAP = {
    "airport":       "Airport",
    "port":          "Port",
    "bus_station":   "Bus",
    "train_station": "Train",
    "station":       "Train",
    "transport_hub": "Hub",
}


def run():
    df = pd.read_csv(INPUT, dtype=str)
    name = df["hub_name"]

    out = pd.DataFrame({
        "unique_id":        "osmhub_" + df["osm_id"],
        "name":             name,
        "name_clean":       clean_name(name),
        "entity_type":      df["hub_type"].str.lower().map(
                                lambda x: HUB_TYPE_MAP.get(x, "Hub")
                            ),
        "lat":              pd.to_numeric(df["lat"], errors="coerce"),
        "lon":              pd.to_numeric(df["lon"], errors="coerce"),
        "iata_code":        df["iata_code"],
        "source":           "osm_hubs",
        "source_id":        df["osm_id"],
        "destination_id":   df["destination_wikidata_id"],
        "destination_name": df["destination_name"],
    })

    # Strip whitespace
    out["name"]       = out["name"].str.strip()
    out["name_clean"] = out["name_clean"].str.strip()

    out = out[out["name"].notna() & (out["name"] != "")]
    out = out.drop_duplicates(subset=["unique_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    print(f"transport  : {len(out)} rows → {OUTPUT}")
    for etype, grp in out.groupby("entity_type"):
        print(f"  {etype:15s}: {len(grp)}")


if __name__ == "__main__":
    run()
