"""
Normalize wikidata_activities.csv into Splink input table.
Output: data/normalized/splink_input/activities.csv
Schema: unique_id, activity_wikidata_id, name, name_clean, activity_type,
        destination_id, destination_name, lat, lon
"""
from pathlib import Path
import pandas as pd

ROOT   = Path(__file__).parents[3]
INPUT  = ROOT / "data/sources/activity/wikidata_activities.csv"
OUTPUT = ROOT / "data/normalized/splink_input/activities.csv"


def clean_name(s: pd.Series) -> pd.Series:
    return (
        s.str.strip()
         .str.lower()
         .str.replace(r"[^\w\s'\-]", "", regex=True)
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )


ACTIVITY_TYPE_MAP = {
    "museum":              "Museum",
    "tourist attraction":  "Tourist Attraction",
    "beach":               "Beach",
    "archaeological site": "Archaeological Site",
    "religious site":      "Religious Site",
    "amusement park":      "Amusement Park",
    "water park":          "Water Park",
    "hiking area":         "Hiking Area",
}


def run():
    df = pd.read_csv(INPUT, dtype=str)

    out = pd.DataFrame({
        "unique_id":         "act_" + df["activity_wikidata_id"],
        "activity_wikidata_id": df["activity_wikidata_id"],
        "name":              df["activity_name"].str.strip(),
        "name_clean":        clean_name(df["activity_name"]),
        "activity_type":     df["activity_type"].str.lower().str.strip()
                                 .map(lambda x: ACTIVITY_TYPE_MAP.get(x, x)),
        "destination_id":    df["destination_wikidata_id"],
        "destination_name":  df["destination_name"],
        "lat":               pd.to_numeric(df["lat"], errors="coerce"),
        "lon":               pd.to_numeric(df["lon"], errors="coerce"),
    })

    # Drop junk rows
    out = out[out["name"].notna() & (out["name"] != "")]
    out = out[out["name_clean"].notna() & (out["name_clean"] != "")]
    out = out.drop_duplicates(subset=["unique_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    print(f"activities: {len(out)} rows → {OUTPUT}")
    for atype, grp in out.groupby("activity_type"):
        print(f"  {atype:25s}: {len(grp):,}")


if __name__ == "__main__":
    run()
