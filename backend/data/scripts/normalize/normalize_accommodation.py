"""
Normalize accommodation/osm.csv into Splink input table.
Output: data/normalized/splink_input/accommodations.csv
Schema: record_id, name, entity_type, lat, lon, star_rating, source, source_id, destination_id, destination_name
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=42)  # fixed seed for reproducibility

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


def clean_star_rating(s: pd.Series) -> pd.Series:
    """
    Standardise OSM star_rating values to float 1–5.
    Handles: '3S'/'4S' (Superior), '4,5' (European decimal), '2024' (bad data).
    Nulls anything that can't be resolved to 1–5 after cleaning.
    """
    cleaned = (
        s.str.strip()
         .str.upper()
         .str.replace(r"[SL]$", "", regex=True)   # strip Superior/Luxury suffix
         .str.replace(",", ".", regex=False)        # European decimal
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    numeric = numeric.where(numeric.between(1, 5))  # null out-of-range values
    return numeric


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
        "star_rating":      clean_star_rating(df["star_rating"].fillna("")),
        "rooms":            pd.to_numeric(df["rooms"], errors="coerce").where(
                                lambda x: x.between(1, 10000)
                            ),
        "source":           "osm_accommodation",
        "source_id":        df["osm_id"],
        "destination_id":   df["destination_wikidata_id"],
        "destination_name": df["destination_name"],
    })

    # Strip whitespace
    out["name"]       = out["name"].str.strip()
    out["name_clean"] = out["name_clean"].str.strip()

    # Drop junk: empty name, null name_clean (symbol-only names)
    out = out[out["name"].notna() & (out["name"] != "")]
    out = out[out["name_clean"].notna() & (out["name_clean"] != "")]
    out = out.drop_duplicates(subset=["unique_id"])

    # Mock-fill missing star_rating: random float 1.0–5.0 (1 decimal place)
    missing_stars = out["star_rating"].isna()
    out.loc[missing_stars, "star_rating"] = (
        (RNG.uniform(1.0, 5.0, missing_stars.sum()) * 10).round() / 10
    )

    # Mock-fill missing rooms: random int 5–300
    missing_rooms = out["rooms"].isna()
    out.loc[missing_rooms, "rooms"] = RNG.integers(5, 301, missing_rooms.sum()).astype(float)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    real_stars = (~missing_stars & out["star_rating"].notna()).sum()
    real_rooms = (~missing_rooms & out["rooms"].notna()).sum()
    print(f"accommodation: {len(out)} rows → {OUTPUT}")
    for etype, grp in out.groupby("entity_type"):
        print(f"  {etype:15s}: {len(grp)}")
    print(f"  star_rating  : {real_stars:,} real  +  {missing_stars.sum():,} mocked")
    print(f"  rooms        : {real_rooms:,} real  +  {missing_rooms.sum():,} mocked")


if __name__ == "__main__":
    run()
