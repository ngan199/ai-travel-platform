"""
Fetch food market venues from Wikidata for each country.
Uses country QIDs from normalized destinations.csv.
Appends to data/sources/venue/national_parks.csv (same schema).
"""
import csv
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parents[3]
OUTPUT = ROOT / "data/sources/venue/national_parks.csv"
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

MARKET_TYPES = {
    "Q330284":    "food market",   # market
    "Q17350442":  "food market",   # public market
    "Q12482":     "food market",   # bazaar
    "Q208485":    "food market",   # farmers market
}


def load_country_qids() -> list[tuple[str, str]]:
    df = pd.read_csv(ROOT / "data/normalized/destinations.csv")
    df = df[df["entity_type"] == "Country"]
    return list(zip(df["destination_id"], df["name"]))


def load_existing_venue_qids() -> set[str]:
    df = pd.read_csv(OUTPUT, usecols=["venue_wikidata_id"])
    return set(df["venue_wikidata_id"])


def sparql_query(qid_batch: list[str], type_qid: str) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT ?venue ?venueLabel ?country ?countryLabel ?lat ?lon
WHERE {{
  VALUES ?country {{ {values} }}
  ?venue wdt:P31  wd:{type_qid} .
  {{ ?venue wdt:P17 ?country . }}
  UNION
  {{ ?venue wdt:P131/wdt:P17 ?country . }}
  OPTIONAL {{
    ?venue wdt:P625 ?coord .
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
    countries  = load_country_qids()
    existing   = load_existing_venue_qids()
    qids       = [q for q, _ in countries]
    name_map   = {q: n for q, n in countries}

    batches = [qids[i:i + BATCH_SIZE] for i in range(0, len(qids), BATCH_SIZE)]
    total_calls = len(batches) * len(MARKET_TYPES)
    print(f"Fetching markets for {len(qids)} countries × {len(MARKET_TYPES)} types "
          f"= {total_calls} queries…")

    new_rows = []
    seen = set()
    call_num = 0

    for type_qid, type_label in MARKET_TYPES.items():
        for i, batch in enumerate(batches):
            call_num += 1
            try:
                bindings = sparql_query(batch, type_qid)
                for b in bindings:
                    vid   = b["venue"]["value"].split("/")[-1]
                    c_qid = b["country"]["value"].split("/")[-1]
                    key   = (vid, c_qid)
                    if vid not in existing and key not in seen:
                        new_rows.append({
                            "venue_wikidata_id":      vid,
                            "venue_name":             b.get("venueLabel", {}).get("value", ""),
                            "venue_type":             type_label,
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
    with OUTPUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerows(new_rows)

    print(f"markets: {len(new_rows)} rows appended → {OUTPUT}")


if __name__ == "__main__":
    run()
