"""
Fetch country-level destination records from Wikidata.
Uses QIDs already present in normalized languages/currencies files.
Queries for name, coordinates, and confirms entity_type = country.
Appends to data/sources/destination/wikidata_destinations.csv.
"""
import csv
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parents[3]
OUTPUT = ROOT / "data/sources/destination/wikidata_destinations.csv"
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


def load_country_qids() -> list[str]:
    lang = pd.read_csv(ROOT / "data/normalized/languages.csv", usecols=["destination_id"])
    curr = pd.read_csv(ROOT / "data/normalized/currencies.csv", usecols=["destination_id"])
    return list(pd.concat([lang, curr])["destination_id"].drop_duplicates())


def load_existing_qids() -> set[str]:
    df = pd.read_csv(OUTPUT, usecols=["wikidata_id"])
    return set(df["wikidata_id"])


def sparql_query(qid_batch: list[str]) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT ?item ?itemLabel ?lat ?lon
WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{
    ?item p:P625 ?coord .
    ?coord psv:P625 ?coordValue .
    ?coordValue wikibase:geoLatitude  ?lat .
    ?coordValue wikibase:geoLongitude ?lon .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
"""
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers=HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    rows = []
    for b in resp.json()["results"]["bindings"]:
        qid = b["item"]["value"].split("/")[-1]
        rows.append({
            "wikidata_id":       qid,
            "name":              b.get("itemLabel", {}).get("value", ""),
            "entity_type":       "country",
            "parent_wikidata_id": "",
            "parent_name":       "",
            "lat":               b.get("lat", {}).get("value", ""),
            "lon":               b.get("lon", {}).get("value", ""),
        })
    return rows


def run():
    all_qids    = load_country_qids()
    existing    = load_existing_qids()
    to_fetch    = [q for q in all_qids if q not in existing]

    print(f"Countries to fetch: {len(to_fetch)}")

    batches = [to_fetch[i:i + BATCH_SIZE] for i in range(0, len(to_fetch), BATCH_SIZE)]
    new_rows = []

    for i, batch in enumerate(batches):
        try:
            rows = sparql_query(batch)
            new_rows.extend(rows)
        except Exception as exc:
            print(f"  batch {i+1} error: {exc}")
        if i < len(batches) - 1:
            time.sleep(1)
        print(f"  batch {i+1}/{len(batches)} → {len(new_rows)} fetched", end="\r")

    print()

    # Append to existing CSV
    with OUTPUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerows(new_rows)

    print(f"countries: {len(new_rows)} rows appended → {OUTPUT}")


if __name__ == "__main__":
    run()
