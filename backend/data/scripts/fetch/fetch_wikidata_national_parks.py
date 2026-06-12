"""
Fetch national parks and nature reserves linked to our destinations via Wikidata SPARQL.
Matches on P17 (country) only — direct, lightweight link.
Queries one park type at a time per batch to avoid server-side timeouts.
Output: data/sources/venue/national_parks.csv
"""
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/venue/national_parks.csv"
FIELDNAMES = [
    "venue_wikidata_id", "venue_name", "venue_type",
    "destination_wikidata_id", "destination_name",
    "lat", "lon",
]

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "travel-ai-platform/1.0 (data-pipeline; contact: trankimngan.dev@gmail.com)",
    "Accept": "application/sparql-results+json",
}
BATCH_SIZE = 20
RETRY_BACKOFF = [10, 30, 60]

PARK_TYPES = {
    "Q46169":  "national park",
    "Q179049": "protected area",
    "Q1970725": "nature reserve",
}


def load_destinations() -> list[tuple[str, str]]:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT wikidata_id, name FROM destinations WHERE entity_type = 'country' ORDER BY name"
        ))
        return [(r[0], r[1]) for r in result]


def sparql_query(qid_batch: list[str], type_qid: str) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT ?park ?parkLabel ?dest ?destLabel ?lat ?lon
WHERE {{
  VALUES ?dest {{ {values} }}
  ?park wdt:P31  wd:{type_qid} .
  ?park wdt:P17  ?dest .
  OPTIONAL {{
    ?park wdt:P625 ?coord .
    BIND(geof:latitude(?coord)  AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }}
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
    total_calls = len(batches) * len(PARK_TYPES)
    call_num = 0

    print(f"Fetching national parks for {len(qids)} countries × {len(PARK_TYPES)} types "
          f"= {total_calls} queries in batches of {BATCH_SIZE}…")

    for type_qid, type_label in PARK_TYPES.items():
        for i, batch in enumerate(batches):
            call_num += 1
            try:
                bindings = sparql_query(batch, type_qid)
                for b in bindings:
                    vid = b["park"]["value"].split("/")[-1]
                    did = b["dest"]["value"].split("/")[-1]
                    key = (vid, did)
                    if key not in seen:
                        all_rows.append({
                            "venue_wikidata_id": vid,
                            "venue_name": b.get("parkLabel", {}).get("value", ""),
                            "venue_type": type_label,
                            "destination_wikidata_id": did,
                            "destination_name": b.get("destLabel", {}).get("value", ""),
                            "lat": b.get("lat", {}).get("value", ""),
                            "lon": b.get("lon", {}).get("value", ""),
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

    print(f"national_parks: {len(all_rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
