"""
Normalize activity/festivals.csv
Output: data/normalized/festivals.csv
Schema: festival_id, name, festival_type, destination_id, destination_name, start_date, end_date
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parents[3]
INPUT = ROOT / "data/sources/activity/festivals.csv"
OUTPUT = ROOT / "data/normalized/festivals.csv"


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

    df["start_date"] = clean_date(df["start_date"].fillna("")).replace("", None)
    df["end_date"] = clean_date(df["end_date"].fillna("")).replace("", None)

    df = df[["festival_id", "name", "festival_type",
             "destination_id", "destination_name", "start_date", "end_date"]]
    df = df.drop_duplicates(subset=["festival_id", "destination_id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"festivals  : {len(df)} rows → {OUTPUT}  (dropped {dropped} unlabelled)")


if __name__ == "__main__":
    run()
