"""
Export Splink cluster results → er.json (Senzing RESOLVED_ENTITY JSONL format).

One JSON object per line, one object per resolved entity (cluster).
All 6 tables written into a single data/output/er.json file.

Schema (per line):
{
  "RESOLVED_ENTITY": {
    "ENTITY_ID":   <int>,          # global sequential across all tables
    "ENTITY_NAME": <str>,          # canonical name (first/primary record)
    "FEATURES": {
      "NAME":        [...],         # all name variants across merged records
      "ADDRESS":     [...],         # lat/lon descriptor where available
      "RECORD_TYPE": [...]          # ontology concept from domain.ttl
    },
    "RECORD_SUMMARY": [...],        # count per DATA_SOURCE
    "RECORDS":        [...]         # one entry per source record
  },
  "RELATED_ENTITIES": []
}
"""
import hashlib
import itertools
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT       = Path(__file__).parents[3]
FINAL      = ROOT / "data/normalized/final"
OUTPUT_DIR = ROOT / "data/output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT     = OUTPUT_DIR / "er.json"

# ── Ontology mappings from domain.ttl ───────────────────────────────────────

# entity_type value → RECORD_TYPE string
RECORD_TYPE_MAP = {
    # destinations
    "Country":      "COUNTRY",
    "City":         "CITY",
    "Region":       "REGION",
    "Province":     "PROVINCE",
    "District":     "DISTRICT",
    "Neighborhood": "NEIGHBORHOOD",
    # venues
    "Venue":        "VENUE",
    "Park":         "NATIONAL_PARK",
    "Market":       "FOOD_MARKET",
    "Restaurant":   "RESTAURANT",
    # accommodations
    "Hotel":        "HOTEL",
    "Hostel":       "HOSTEL",
    "Resort":       "RESORT",
    "Guesthouse":   "GUESTHOUSE",
    "Villa":        "VILLA",
    "Camping":      "CAMPING",
    "Lodging":      "LODGING",
    # transport hubs
    "Airport":      "AIRPORT",
    "Port":         "PORT",
    "Bus":          "BUS_STATION",
    "Train":        "TRAIN_STATION",
    "Hub":          "TRANSPORT_HUB",
    # activities
    "Museum":             "MUSEUM",
    "Tourist Attraction": "TOURIST_ATTRACTION",
    "Beach":              "BEACH",
    "Archaeological Site":"ARCHAEOLOGICAL_SITE",
    "Religious Site":     "RELIGIOUS_SITE",
    "Amusement Park":     "AMUSEMENT_PARK",
    "Water Park":         "WATER_PARK",
    "Hiking Area":        "HIKING_AREA",
    # festivals
    "Festival": "FESTIVAL",
    "Event":    "EVENT",
}

# source column value → DATA_SOURCE string
SOURCE_MAP = {
    "osm_venues":        "OSM_VENUE",
    "national_parks":    "NATIONAL_PARK",
    "top_attractions":   "TOP_ATTRACTION",
    "osm_accommodation": "OSM_ACCOMMODATION",
    "osm_hubs":          "OSM_HUB",
    "wikidata":          "WIKIDATA",
}

# fallback DATA_SOURCE per table when no source column
TABLE_SOURCE = {
    "destinations": "WIKIDATA_DESTINATION",
    "venues":       "OSM_VENUE",
    "accommodations": "OSM_ACCOMMODATION",
    "transport_hubs": "OSM_HUB",
    "festivals":    "WIKIDATA_FESTIVAL",
    "activities":   "WIKIDATA_ACTIVITY",
}


def record_id(unique_id: str) -> str:
    """SHA1 hash of unique_id as RECORD_ID."""
    return hashlib.sha1(unique_id.encode()).hexdigest()


def get_data_source(row: pd.Series, table: str) -> str:
    if "source" in row.index and pd.notna(row["source"]):
        return SOURCE_MAP.get(str(row["source"]).strip(), str(row["source"]).upper())
    return TABLE_SOURCE[table]


def get_record_type(row: pd.Series, table: str) -> str:
    for col in ("entity_type", "activity_type", "festival_type"):
        if col in row.index and pd.notna(row[col]):
            val = str(row[col]).strip()
            if val in RECORD_TYPE_MAP:
                return RECORD_TYPE_MAP[val]
    return TABLE_SOURCE[table].split("_")[0]


def format_address(row: pd.Series) -> str | None:
    lat = row.get("lat")
    lon = row.get("lon")
    dest = row.get("destination_name") or row.get("parent_name")
    if pd.notna(lat) and pd.notna(lon):
        parts = []
        if dest and pd.notna(dest):
            parts.append(str(dest))
        parts.append(f"{float(lat):.6f}, {float(lon):.6f}")
        return ", ".join(parts)
    return None


def build_entity(
    cluster_id: str,
    records: pd.DataFrame,
    entity_id: int,
    table: str,
    feat_id_counter: itertools.count,
    internal_id_counter: itertools.count,
) -> dict:
    # Sort: primary record first (singleton or first alphabetically by unique_id)
    records = records.sort_values("unique_id").reset_index(drop=True)
    primary = records.iloc[0]

    # ── NAME feature ────────────────────────────────────────────────
    all_names = (
        records["name"].dropna().astype(str).str.strip()
        .loc[lambda s: s != ""].unique().tolist()
    )
    canonical_name = str(primary.get("name", "")).strip() or cluster_id

    name_feat_id = next(feat_id_counter)
    name_feat_desc_values = []
    seen_names = set()
    for n in all_names:
        if n not in seen_names:
            fid = name_feat_id if n == canonical_name else next(feat_id_counter)
            name_feat_desc_values.append({"FEAT_DESC": n, "LIB_FEAT_ID": fid})
            seen_names.add(n)

    name_feature = [{
        "FEAT_DESC": canonical_name,
        "LIB_FEAT_ID": name_feat_id,
        "USAGE_TYPE": "PRIMARY",
        "FEAT_DESC_VALUES": name_feat_desc_values,
    }]

    # ── RECORD_TYPE feature ─────────────────────────────────────────
    rtype = get_record_type(primary, table)
    rt_feat_id = next(feat_id_counter)
    record_type_feature = [{
        "FEAT_DESC": rtype,
        "LIB_FEAT_ID": rt_feat_id,
        "FEAT_DESC_VALUES": [{"FEAT_DESC": rtype, "LIB_FEAT_ID": rt_feat_id}],
    }]

    # ── ADDRESS feature (lat/lon) ────────────────────────────────────
    address_feature = []
    seen_addrs = set()
    for _, row in records.iterrows():
        addr = format_address(row)
        if addr and addr not in seen_addrs:
            fid = next(feat_id_counter)
            address_feature.append({
                "FEAT_DESC": addr,
                "LIB_FEAT_ID": fid,
                "FEAT_DESC_VALUES": [{"FEAT_DESC": addr, "LIB_FEAT_ID": fid}],
            })
            seen_addrs.add(addr)

    features: dict = {"NAME": name_feature, "RECORD_TYPE": record_type_feature}
    if address_feature:
        features["ADDRESS"] = address_feature

    # ── RECORD_SUMMARY ───────────────────────────────────────────────
    source_counts: dict[str, int] = defaultdict(int)
    for _, row in records.iterrows():
        source_counts[get_data_source(row, table)] += 1
    record_summary = [
        {"DATA_SOURCE": src, "RECORD_COUNT": cnt}
        for src, cnt in source_counts.items()
    ]

    # ── RECORDS ──────────────────────────────────────────────────────
    rec_list = []
    for i, (_, row) in enumerate(records.iterrows()):
        is_primary = i == 0
        rec_list.append({
            "DATA_SOURCE":      get_data_source(row, table),
            "RECORD_ID":        record_id(str(row["unique_id"])),
            "INTERNAL_ID":      next(internal_id_counter),
            "MATCH_KEY":        "" if is_primary else "+NAME",
            "MATCH_LEVEL_CODE": "" if is_primary else "RESOLVED",
            "ERRULE_CODE":      "" if is_primary else "SPLINK_CLUSTER",
        })

    return {
        "RESOLVED_ENTITY": {
            "ENTITY_ID":   entity_id,
            "ENTITY_NAME": canonical_name,
            "FEATURES":    features,
            "RECORD_SUMMARY": record_summary,
            "RECORDS":     rec_list,
        },
        "RELATED_ENTITIES": [],
    }


def export_table(
    table: str,
    entity_id_counter: itertools.count,
    feat_id_counter: itertools.count,
    internal_id_counter: itertools.count,
    out_f,
) -> int:
    df = pd.read_csv(FINAL / f"{table}.csv", dtype=str, low_memory=False)
    for col in ("lat", "lon"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    n_written = 0
    for cluster_id, group in df.groupby("cluster_id"):
        entity = build_entity(
            cluster_id=cluster_id,
            records=group,
            entity_id=next(entity_id_counter),
            table=table,
            feat_id_counter=feat_id_counter,
            internal_id_counter=internal_id_counter,
        )
        out_f.write(json.dumps(entity, ensure_ascii=False) + "\n")
        n_written += 1

    print(f"  {table}: {len(df):,} records → {n_written:,} entities")
    return n_written


if __name__ == "__main__":
    print(f"=== Export er.json ===")

    entity_id_counter   = itertools.count(1)
    feat_id_counter     = itertools.count(1)
    internal_id_counter = itertools.count(1)

    total = 0
    with OUTPUT.open("w", encoding="utf-8") as f:
        for table in ["destinations", "venues", "accommodations", "transport_hubs", "festivals", "activities"]:
            total += export_table(table, entity_id_counter, feat_id_counter, internal_id_counter, f)

    print(f"\n  {total:,} total entities → {OUTPUT.relative_to(ROOT)}")
