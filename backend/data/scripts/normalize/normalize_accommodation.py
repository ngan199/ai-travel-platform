"""
Normalize accommodation/osm.csv into Splink input table.
Output: data/normalized/splink_input/accommodations.csv
Schema: record_id, name, entity_type, lat, lon, star_rating, source, source_id, destination_id, destination_name
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).parents[3]
INPUT = ROOT / "data/sources/accommodation/osm.csv"
OUTPUT = ROOT / "data/normalized/splink_input/accommodations.csv"

def clean_name(s: pd.Series) -> pd.Series:
    return (
        s.str.strip()
         .str.lower()
         .str.replace(r"[^\w\s'\-]", "", regex=True)
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )


ACCOMMODATION_TYPE_MAP = {
    "hotel":       "Hotel",
    "hostel":      "Hostel",
    "resort":      "Resort",
    "guest_house": "Guesthouse",
    "motel":       "Hotel",
    "apartment":   "Villa",
    "chalet":      "Villa",
    "camp_site":   "Camping",
}


def run():
    df = pd.read_csv(INPUT, dtype=str)
    name = df["accommodation_name"]

    out = pd.DataFrame({
        "unique_id":        "osmacc_" + df["osm_id"],
        "name":             name,
        "name_clean":       clean_name(name),
        "entity_type":      df["accommodation_type"].str.lower().map(
                                lambda x: ACCOMMODATION_TYPE_MAP.get(x, "Lodging")
                            ),
        "lat":              pd.to_numeric(df["lat"], errors="coerce"),
        "lon":              pd.to_numeric(df["lon"], errors="coerce"),
        "star_rating":      pd.to_numeric(df["star_rating"], errors="coerce"),
        "source":           "osm_accommodation",
        "source_id":        df["osm_id"],
        "destination_id":   df["destination_wikidata_id"],
        "destination_name": df["destination_name"],
    })

    out = out[out["name"].notna() & (out["name"].str.strip() != "")]
    out = out.drop_duplicates(subset=["unique_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    print(f"accommodation: {len(out)} rows → {OUTPUT}")
    for etype, grp in out.groupby("entity_type"):
        print(f"  {etype:15s}: {len(grp)}")


if __name__ == "__main__":
    run()
