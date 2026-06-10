"""
Merge 3 venue sources into a unified Splink input table.
Sources:
  venue/national_parks.csv    → NationalPark
  venue/top_attractions.csv   → Venue (wikidata-linked)
  venue/osm_venues.csv        → Venue (OSM)
Output: data/normalized/splink_input/venues.csv
Schema: record_id, name, entity_type, lat, lon, source, source_id, destination_id, destination_name
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).parents[3]
SOURCES = ROOT / "data/sources"
OUTPUT = ROOT / "data/normalized/splink_input/venues.csv"

def clean_name(s: pd.Series) -> pd.Series:
    return (
        s.str.strip()
         .str.lower()
         .str.replace(r"[^\w\s'\-]", "", regex=True)
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )


VENUE_TYPE_MAP = {
    # OSM tourism
    "attraction":       "Venue",
    "museum":           "Venue",
    "artwork":          "Venue",
    "gallery":          "Venue",
    "viewpoint":        "Venue",
    "theme_park":       "Venue",
    # OSM amenity
    "place_of_worship": "Venue",
    "theatre":          "Venue",
    "cinema":           "Venue",
    # OSM leisure
    "park":             "Venue",
    "nature_reserve":   "Park",
    # OSM historic
    "monument":         "Venue",
    "castle":           "Venue",
    "ruins":            "Venue",
    # national parks source
    "national park":    "Park",
    "nature park":      "Park",
    "national_park":    "Park",
    "nature reserve":   "Park",
    "protected area":   "Park",
    # top_attractions categories
    "historic site":    "Venue",
    "natural attraction": "Venue",
    "religious site":   "Venue",
    "cultural site":    "Venue",
    "beach":            "Venue",
    "market":           "Market",
    "food market":      "Market",
    "restaurant":       "Restaurant",
    "entertainment":    "Venue",
    "shopping":         "Venue",
    "park":             "Venue",
    "landmark":         "Venue",
}


def map_type(val: str) -> str:
    if pd.isna(val) or val == "":
        return "Venue"
    return VENUE_TYPE_MAP.get(str(val).strip().lower(), "Venue")


def from_national_parks() -> pd.DataFrame:
    df = pd.read_csv(SOURCES / "venue/national_parks.csv", dtype=str)
    name = df["venue_name"]
    return pd.DataFrame({
        "unique_id":        "np_" + df["venue_wikidata_id"],
        "name":             name,
        "name_clean":       clean_name(name),
        "entity_type":      df["venue_type"].map(map_type),
        "lat":              pd.to_numeric(df["lat"], errors="coerce"),
        "lon":              pd.to_numeric(df["lon"], errors="coerce"),
        "source":           "national_parks",
        "source_id":        df["venue_wikidata_id"],
        "destination_id":   df["destination_wikidata_id"],
        "destination_name": df["destination_name"],
    })


def from_top_attractions() -> pd.DataFrame:
    df = pd.read_csv(SOURCES / "venue/top_attractions.csv", dtype=str)
    name = df["venue_name"]
    return pd.DataFrame({
        "unique_id":        "ta_" + df["venue_wikidata_id"],
        "name":             name,
        "name_clean":       clean_name(name),
        "entity_type":      df["venue_category"].map(map_type),
        "lat":              float("nan"),
        "lon":              float("nan"),
        "source":           "top_attractions",
        "source_id":        df["venue_wikidata_id"],
        "destination_id":   df["destination_wikidata_id"],
        "destination_name": df["destination_name"],
    })


def from_osm_venues() -> pd.DataFrame:
    df = pd.read_csv(SOURCES / "venue/osm_venues.csv", dtype=str)
    name = df["venue_name"]
    return pd.DataFrame({
        "unique_id":        "osm_" + df["osm_id"],
        "name":             name,
        "name_clean":       clean_name(name),
        "entity_type":      df["venue_type"].map(map_type),
        "lat":              pd.to_numeric(df["lat"], errors="coerce"),
        "lon":              pd.to_numeric(df["lon"], errors="coerce"),
        "source":           "osm_venues",
        "source_id":        df["osm_id"],
        "destination_id":   df["destination_wikidata_id"],
        "destination_name": df["destination_name"],
    })


def run():
    parts = [from_national_parks(), from_top_attractions(), from_osm_venues()]
    df = pd.concat(parts, ignore_index=True)

    df = df[df["name"].notna() & (df["name"].str.strip() != "")]
    df = df.drop_duplicates(subset=["unique_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)

    print(f"venues     : {len(df)} rows → {OUTPUT}")
    print(f"  national_parks   : {(df['source'] == 'national_parks').sum()}")
    print(f"  top_attractions  : {(df['source'] == 'top_attractions').sum()}")
    print(f"  osm_venues       : {(df['source'] == 'osm_venues').sum()}")


if __name__ == "__main__":
    run()
