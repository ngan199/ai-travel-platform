"""
Fetch administrative sub-regions of destinations already in the DB via Wikidata SPARQL.
Uses P131 (located in administrative territorial entity) to find children.
Only fetches items whose direct parent (P131) is one of our destination QIDs.
Output: data/sources/destination/wikidata_regions.csv

Batches QIDs in groups of 50 to stay within SPARQL query limits.
Adds 1 s delay between batches to respect Wikidata rate limits.
"""
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/destination/wikidata_regions.csv"
FIELDNAMES = [
    "wikidata_id", "name", "entity_type",
    "parent_wikidata_id", "parent_name",
    "lat", "lon",
]

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "travel-ai-platform/1.0 (data-pipeline; contact: trankimngan.dev@gmail.com)",
    "Accept": "application/sparql-results+json",
}
BATCH_SIZE = 50

INSTANCE_FILTER = """
  VALUES ?type {
    wd:Q515       # city
    wd:Q1093829   # municipality
    wd:Q3957      # town
    wd:Q532       # village
    wd:Q11618634  # district
    wd:Q856076    # quarter
    wd:Q123705    # neighbourhood
    wd:Q1549591   # big city
    wd:Q13220204  # county
    wd:Q21167512  # city district
  }
"""


def load_destination_qids() -> list[tuple[str, str]]:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT wikidata_id, name FROM destinations ORDER BY entity_type, name"
        ))
        return [(r[0], r[1]) for r in result]


def sparql_query(qid_batch: list[str]) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT
  ?item ?itemLabel ?type ?typeLabel ?parent ?parentLabel
  ?lat ?lon
WHERE {{
  VALUES ?parent {{ {values} }}
  ?item wdt:P131 ?parent .
  ?item wdt:P31  ?type .
  {INSTANCE_FILTER}
  OPTIONAL {{
    ?item p:P625 ?coord .
    ?coord psv:P625 ?coordValue .
    ?coordValue wikibase:geoLatitude  ?lat .
    ?coordValue wikibase:geoLongitude ?lon .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 2000
"""
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers=HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    bindings = resp.json()["results"]["bindings"]
    rows = []
    for b in bindings:
        item_qid = b["item"]["value"].split("/")[-1]
        parent_qid = b["parent"]["value"].split("/")[-1]
        rows.append({
            "wikidata_id": item_qid,
            "name": b.get("itemLabel", {}).get("value", ""),
            "entity_type": b.get("typeLabel", {}).get("value", ""),
            "parent_wikidata_id": parent_qid,
            "parent_name": b.get("parentLabel", {}).get("value", ""),
            "lat": b.get("lat", {}).get("value", ""),
            "lon": b.get("lon", {}).get("value", ""),
        })
    return rows


def run():
    destinations = load_destination_qids()
    existing_qids = {qid for qid, _ in destinations}
    qids = [qid for qid, _ in destinations]

    all_rows = []
    seen = set()

    batches = [qids[i:i + BATCH_SIZE] for i in range(0, len(qids), BATCH_SIZE)]
    print(f"Fetching regions for {len(qids)} destinations in {len(batches)} batches…")

    for i, batch in enumerate(batches):
        try:
            rows = sparql_query(batch)
            for row in rows:
                if row["wikidata_id"] not in existing_qids and row["wikidata_id"] not in seen:
                    all_rows.append(row)
                    seen.add(row["wikidata_id"])
        except Exception as exc:
            print(f"  batch {i+1} error: {exc}")
        if i < len(batches) - 1:
            time.sleep(1)
        print(f"  batch {i+1}/{len(batches)} → {len(all_rows)} total so far", end="\r")

    print()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"wikidata_regions: {len(all_rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
