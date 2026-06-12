"""
Fetch structured activity venues from Wikidata per country.
Uses country QIDs from normalized destinations.csv.
Appends to data/sources/activity/wikidata_activities.csv.

Activity types fetched:
  Q33506   museum
  Q11707   restaurant (excluded — covered by venues)
  Q570116  tourist attraction
  Q1007870 beach
  Q46169   hiking trail (mountain)
  Q839954  archaeological site
  Q24398318 religious place
  Q483110  amphitheatre / performance venue
  Q1761038 water park
  Q35998   amusement park
"""
import csv
import time
from pathlib import Path

import pandas as pd
import requests

ROOT   = Path(__file__).parents[3]
OUTPUT = ROOT / "data/sources/activity/wikidata_activities.csv"
FIELDNAMES = [
    "activity_wikidata_id", "activity_name", "activity_type",
    "destination_wikidata_id", "destination_name",
    "lat", "lon",
]

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "travel-ai-platform/1.0 (data-pipeline; contact: trankimngan.dev@gmail.com)",
    "Accept": "application/sparql-results+json",
}
BATCH_SIZE    = 10   # smaller — direct P31 queries are still broad
RETRY_BACKOFF = [10, 30, 60]

ACTIVITY_TYPES = {
    "Q33506":    "museum",
    "Q570116":   "tourist attraction",
    "Q1007870":  "beach",
    "Q839954":   "archaeological site",
    "Q24398318": "religious site",
    "Q35998":    "amusement park",
    "Q1761038":  "water park",
    "Q46169":    "hiking area",
}


def load_country_qids() -> list[tuple[str, str]]:
    df = pd.read_csv(ROOT / "data/normalized/destinations.csv")
    df = df[df["entity_type"] == "Country"]
    return list(zip(df["destination_id"], df["name"]))


def load_existing_ids() -> set[str]:
    if not OUTPUT.exists():
        return set()
    df = pd.read_csv(OUTPUT, usecols=["activity_wikidata_id"])
    return set(df["activity_wikidata_id"])


def sparql_query(qid_batch: list[str], type_qid: str) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT ?item ?itemLabel ?country ?countryLabel ?lat ?lon
WHERE {{
  VALUES ?country {{ {values} }}
  ?item wdt:P31 wd:{type_qid} .
  {{ ?item wdt:P17 ?country . }}
  UNION
  {{ ?item wdt:P131/wdt:P17 ?country . }}
  OPTIONAL {{
    ?item wdt:P625 ?coord .
    BIND(geof:latitude(?coord)  AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 500
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
    return []


def run():
    countries = load_country_qids()
    existing  = load_existing_ids()
    qids      = [q for q, _ in countries]
    name_map  = {q: n for q, n in countries}

    batches     = [qids[i:i + BATCH_SIZE] for i in range(0, len(qids), BATCH_SIZE)]
    total_calls = len(batches) * len(ACTIVITY_TYPES)
    print(f"Fetching activities for {len(qids)} countries × {len(ACTIVITY_TYPES)} types "
          f"= {total_calls} queries…")

    new_rows = []
    seen     = set()
    call_num = 0

    for type_qid, type_label in ACTIVITY_TYPES.items():
        for i, batch in enumerate(batches):
            call_num += 1
            try:
                bindings = sparql_query(batch, type_qid)
                for b in bindings:
                    aid   = b["item"]["value"].split("/")[-1]
                    c_qid = b["country"]["value"].split("/")[-1]
                    key   = (aid, c_qid)
                    if aid not in existing and key not in seen:
                        new_rows.append({
                            "activity_wikidata_id":   aid,
                            "activity_name":          b.get("itemLabel", {}).get("value", ""),
                            "activity_type":          type_label,
                            "destination_wikidata_id": c_qid,
                            "destination_name":       name_map.get(c_qid, ""),
                            "lat":                    b.get("lat", {}).get("value", ""),
                            "lon":                    b.get("lon", {}).get("value", ""),
                        })
                        seen.add(key)
            except Exception as exc:
                print(f"\n  [{call_num}/{total_calls}] {type_label} batch {i+1}: {exc}")
            if call_num < total_calls:
                time.sleep(1)
            print(f"  [{call_num}/{total_calls}] {type_label} → {len(new_rows)} total", end="\r")

    print()

    write_header = not OUTPUT.exists()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)

    print(f"activities: {len(new_rows)} rows appended → {OUTPUT}")


if __name__ == "__main__":
    run()
