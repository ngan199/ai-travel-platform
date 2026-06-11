"""
Normalize all 6 knowledge/content source files (Wikivoyage + visa notes).
These are content tables linked to destinations — not Splink entity-resolution targets.

Outputs (data/normalized/):
  activities.csv       — do/see sections per destination
  transport_guides.csv — get_in/get_around sections per destination
  cuisines.csv         — eat section + street_food flag per destination
  cultural_norms.csv   — respect + local_laws text per destination
  safety_tips.csv      — stay_safe text per destination
  practical_info.csv   — practical notes + visa boolean flags per destination

All outputs:
  - wikidata_id → destination_id
  - text stripped of wiki section headers (==Heading==)
  - leading/trailing whitespace removed
  - null/empty text rows dropped
  - boolean columns coerced to bool
"""
import re
from pathlib import Path
import pandas as pd

ROOT    = Path(__file__).parents[3]
SOURCES = ROOT / "data/sources"
OUT     = ROOT / "data/normalized"

BOOL_MAP = {"true": True, "false": False, "1": True, "0": False}


def strip_wiki_headers(s: pd.Series) -> pd.Series:
    """Remove ==Heading== and === Heading === lines, then strip."""
    return (
        s.str.replace(r"={2,}[^=\n]+={2,}", "", regex=True)
         .str.replace(r"\n{3,}", "\n\n", regex=True)
         .str.strip()
    )


def coerce_bool(s: pd.Series) -> pd.Series:
    return s.str.lower().map(BOOL_MAP)


def normalize_activities():
    df = pd.read_csv(SOURCES / "activity/wikivoyage.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["section_text"] = strip_wiki_headers(df["section_text"].fillna(""))
    df = df[df["section_text"] != ""]
    df = df[["destination_id", "destination_name", "section_type", "section_text"]]
    df = df.drop_duplicates(subset=["destination_id", "section_type"])
    out = OUT / "activities.csv"
    df.to_csv(out, index=False)
    print(f"activities   : {len(df)} rows → {out}")
    print(f"  section_types: {sorted(df['section_type'].unique().tolist())}")


def normalize_transport_guides():
    df = pd.read_csv(SOURCES / "transport/wikivoyage.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["section_text"] = strip_wiki_headers(df["section_text"].fillna(""))
    df = df[df["section_text"] != ""]
    df = df[["destination_id", "destination_name", "section_type", "section_text"]]
    df = df.drop_duplicates(subset=["destination_id", "section_type"])
    out = OUT / "transport_guides.csv"
    df.to_csv(out, index=False)
    print(f"transport_guides: {len(df)} rows → {out}")
    print(f"  section_types: {sorted(df['section_type'].unique().tolist())}")


def normalize_cuisines():
    df = pd.read_csv(SOURCES / "cuisine/wikivoyage.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["eat_section_text"] = strip_wiki_headers(df["eat_section_text"].fillna(""))
    df["street_food_available"] = coerce_bool(df["street_food_available"].fillna("false"))
    df = df[df["eat_section_text"] != ""]
    df = df[["destination_id", "destination_name", "eat_section_text", "street_food_available"]]
    df = df.drop_duplicates(subset=["destination_id"])
    out = OUT / "cuisines.csv"
    df.to_csv(out, index=False)
    print(f"cuisines     : {len(df)} rows → {out}")


def normalize_cultural_norms():
    df = pd.read_csv(SOURCES / "cultural_norm/wikivoyage.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    for col in ("respect_text", "local_laws_text"):
        df[col] = strip_wiki_headers(df[col].fillna(""))
        df[col] = df[col].replace("", None)
    # Keep rows where at least one text column is non-null
    df = df[df["respect_text"].notna() | df["local_laws_text"].notna()]
    df = df[["destination_id", "destination_name", "respect_text", "local_laws_text"]]
    df = df.drop_duplicates(subset=["destination_id"])
    out = OUT / "cultural_norms.csv"
    df.to_csv(out, index=False)
    print(f"cultural_norms: {len(df)} rows → {out}")


def normalize_safety_tips():
    df = pd.read_csv(SOURCES / "safety_tip/wikivoyage.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["stay_safe_text"] = strip_wiki_headers(df["stay_safe_text"].fillna(""))
    df = df[df["stay_safe_text"] != ""]
    df = df[["destination_id", "destination_name", "stay_safe_text"]]
    df = df.drop_duplicates(subset=["destination_id"])
    out = OUT / "safety_tips.csv"
    df.to_csv(out, index=False)
    print(f"safety_tips  : {len(df)} rows → {out}")


def normalize_practical_info():
    df = pd.read_csv(SOURCES / "practical_info/visa_notes.csv", dtype=str)
    df = df.rename(columns={"wikidata_id": "destination_id"})
    df["practical_notes_text"] = strip_wiki_headers(df["practical_notes_text"].fillna(""))
    df["practical_notes_text"] = df["practical_notes_text"].replace("", None)
    for col in ("mentions_visa", "mentions_visa_on_arrival", "mentions_visa_free"):
        df[col] = coerce_bool(df[col].fillna("false"))
    df = df[df["practical_notes_text"].notna()]
    df = df[["destination_id", "destination_name",
             "practical_notes_text",
             "mentions_visa", "mentions_visa_on_arrival", "mentions_visa_free"]]
    df = df.drop_duplicates(subset=["destination_id"])
    out = OUT / "practical_info.csv"
    df.to_csv(out, index=False)
    print(f"practical_info: {len(df)} rows → {out}")


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    normalize_activities()
    normalize_transport_guides()
    normalize_cuisines()
    normalize_cultural_norms()
    normalize_safety_tips()
    normalize_practical_info()


if __name__ == "__main__":
    run()
