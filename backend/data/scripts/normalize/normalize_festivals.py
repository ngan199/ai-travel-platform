"""
Normalize activity/festivals.csv
Output:
  data/normalized/festivals.csv              (reference)
  data/normalized/splink_input/festivals.csv (Splink-ready)
Schema: festival_id, name, festival_type, destination_id, destination_name, start_date, end_date
Splink schema adds: unique_id, name_clean
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parents[3]
INPUT  = ROOT / "data/sources/activity/festivals.csv"
OUTPUT = ROOT / "data/normalized/festivals.csv"
OUTPUT_SPLINK = ROOT / "data/normalized/splink_input/festivals.csv"


def clean_name(s: pd.Series) -> pd.Series:
    return (
        s.str.strip()
         .str.lower()
         .str.replace(r"[^\w\s'\-]", "", regex=True)
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )


FESTIVAL_TYPE_MAP = {
    "festival":            "Festival",
    "festival occurrence": "Festival",
    "recurring event":     "Festival",
    "ceremony":            "Event",
    "party":               "Event",
}

# Types with no travel relevance — drop entirely
DROP_TYPES = {"english country house", "discothèque"}


def clean_date(s: pd.Series) -> pd.Series:
    return s.str.replace(r"T\d{2}:\d{2}:\d{2}Z$", "", regex=True).str.strip()


def run():
    df = pd.read_csv(INPUT, dtype=str)

    # Drop rows where festival_name was never resolved (name == QID)
    mask = df["festival_name"] == df["festival_wikidata_id"]
    dropped = mask.sum()
    df = df[~mask].copy()

    df = df.rename(columns={
        "festival_wikidata_id":  "festival_id",
        "destination_wikidata_id": "destination_id",
        "festival_name":         "name",
    })

    # Drop irrelevant types
    df = df[~df["festival_type"].str.lower().isin(DROP_TYPES)].copy()

    # Map festival_type to ontology concepts
    df["festival_type"] = df["festival_type"].str.lower().map(
        lambda x: FESTIVAL_TYPE_MAP.get(x, "Festival")
    )

    df["name"] = df["name"].str.strip()
    df["start_date"] = clean_date(df["start_date"].fillna("")).replace("", None)
    df["end_date"] = clean_date(df["end_date"].fillna("")).replace("", None)

    df = df[["festival_id", "name", "festival_type",
             "destination_id", "destination_name", "start_date", "end_date"]]
    df = df.drop_duplicates(subset=["festival_id", "destination_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"festivals  : {len(df)} rows → {OUTPUT}  (dropped {dropped} unlabelled)")

    # Splink-ready version
    sp = df.copy()
    sp.insert(0, "unique_id", "fest_" + sp["festival_id"])
    sp.insert(2, "name_clean", clean_name(sp["name"]))
    sp = sp[sp["name_clean"].notna() & (sp["name_clean"] != "")]
    OUTPUT_SPLINK.parent.mkdir(parents=True, exist_ok=True)
    sp.to_csv(OUTPUT_SPLINK, index=False)
    print(f"festivals (splink) : {len(sp)} rows → {OUTPUT_SPLINK}")


if __name__ == "__main__":
    run()
