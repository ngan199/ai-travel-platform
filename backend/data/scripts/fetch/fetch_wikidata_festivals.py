"""
Fetch festivals and recurring events linked to our destinations via Wikidata SPARQL.
Links via P276 (location) = one of our destination QIDs.
Queries one festival type at a time per batch to avoid server-side timeouts.
Output: data/sources/activity/festivals.csv
"""
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/activity/festivals.csv"
FIELDNAMES = [
    "festival_wikidata_id", "festival_name", "festival_type",
    "destination_wikidata_id", "destination_name",
    "start_date", "end_date", "inception",
]

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "travel-ai-platform/1.0 (data-pipeline; contact: trankimngan.dev@gmail.com)",
    "Accept": "application/sparql-results+json",
}
BATCH_SIZE = 20
RETRY_BACKOFF = [10, 30, 60]

FESTIVAL_TYPES = {
    "Q132241":   "festival",
    "Q2627975":  "music festival",
    "Q1228895":  "film festival",
    "Q200538":   "arts festival",
    "Q1343246":  "cultural festival",
}


def load_destinations() -> list[tuple[str, str]]:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT wikidata_id, name FROM destinations ORDER BY name"
        ))
        return [(r[0], r[1]) for r in result]


def sparql_query(qid_batch: list[str], type_qid: str) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT ?festival ?festivalLabel ?dest ?destLabel ?startDate ?endDate ?inception
WHERE {{
  VALUES ?dest {{ {values} }}
  ?festival wdt:P31  wd:{type_qid} .
  ?festival wdt:P276 ?dest .
  OPTIONAL {{ ?festival wdt:P580 ?startDate . }}
  OPTIONAL {{ ?festival wdt:P582 ?endDate . }}
  OPTIONAL {{ ?festival wdt:P571 ?inception . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 1000
"""
    for attempt, wait in enumerate(RETRY_BACKOFF + [None]):
        try:
            resp = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=90,
            )
            resp.raise_for_status()
            return resp.json()["results"]["bindings"]
        except Exception as exc:
            if wait is None:
                raise
            print(f"\n    retry {attempt+1} after {wait}s ({exc})")
            time.sleep(wait)


def run():
    destinations = load_destinations()
    qids = [qid for qid, _ in destinations]
    batches = [qids[i:i + BATCH_SIZE] for i in range(0, len(qids), BATCH_SIZE)]

    all_rows = []
    seen = set()
    total_calls = len(batches) * len(FESTIVAL_TYPES)
    call_num = 0

    print(f"Fetching festivals for {len(qids)} destinations × {len(FESTIVAL_TYPES)} types "
          f"= {total_calls} queries in batches of {BATCH_SIZE}…")

    for type_qid, type_label in FESTIVAL_TYPES.items():
        for i, batch in enumerate(batches):
            call_num += 1
            try:
                bindings = sparql_query(batch, type_qid)
                for b in bindings:
                    fid = b["festival"]["value"].split("/")[-1]
                    did = b["dest"]["value"].split("/")[-1]
                    key = (fid, did)
                    if key not in seen:
                        all_rows.append({
                            "festival_wikidata_id": fid,
                            "festival_name": b.get("festivalLabel", {}).get("value", ""),
                            "festival_type": type_label,
                            "destination_wikidata_id": did,
                            "destination_name": b.get("destLabel", {}).get("value", ""),
                            "start_date": b.get("startDate", {}).get("value", ""),
                            "end_date": b.get("endDate", {}).get("value", ""),
                            "inception": b.get("inception", {}).get("value", ""),
                        })
                        seen.add(key)
            except Exception as exc:
                print(f"\n  [{call_num}/{total_calls}] {type_label} batch {i+1}: {exc}")
            if call_num < total_calls:
                time.sleep(1)
            print(f"  [{call_num}/{total_calls}] {type_label} → {len(all_rows)} total", end="\r")

    print()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"festivals: {len(all_rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
