"""
Fetch first-level administrative divisions from Wikidata per country.
Uses Q10864048 (first-level administrative country subdivision) — broad superclass
that covers US states, French régions, German Länder, Chinese provinces, etc.
Uses P131 (located in) = country to find items directly inside each country.
Appends to data/sources/destination/wikidata_destinations.csv.
"""
import csv
import time
from pathlib import Path

import pandas as pd
import requests

ROOT   = Path(__file__).parents[3]
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
BATCH_SIZE    = 10   # smaller — broader query is heavier
RETRY_BACKOFF = [10, 30, 60]


def load_country_qids() -> list[tuple[str, str]]:
    df = pd.read_csv(ROOT / "data/normalized/destinations.csv")
    df = df[df["entity_type"] == "Country"]
    return list(zip(df["destination_id"], df["name"]))


def load_existing_qids() -> set[str]:
    df = pd.read_csv(OUTPUT, usecols=["wikidata_id"])
    return set(df["wikidata_id"])


def sparql_query(qid_batch: list[str]) -> list[dict]:
    values = " ".join(f"wd:{q}" for q in qid_batch)
    query = f"""
SELECT DISTINCT ?item ?itemLabel ?country ?countryLabel ?lat ?lon
WHERE {{
  VALUES ?country {{ {values} }}
  ?item wdt:P131 ?country .
  ?item wdt:P31/wdt:P279* wd:Q10864048 .
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
    existing  = load_existing_qids()
    qids      = [q for q, _ in countries]
    name_map  = {q: n for q, n in countries}

    # Remove existing province/region/district rows from source so we can replace them
    df_src = pd.read_csv(OUTPUT, dtype=str)
    keep_types = {"country", "city", "neighborhood"}
    df_src = df_src[df_src["entity_type"].str.lower().isin(keep_types)]
    df_src.to_csv(OUTPUT, index=False)
    existing = set(df_src["wikidata_id"])
    print(f"Cleared old province/region/district rows. {len(df_src)} rows kept in source.")

    batches     = [qids[i:i + BATCH_SIZE] for i in range(0, len(qids), BATCH_SIZE)]
    total_calls = len(batches)
    print(f"Fetching first-level admin divisions for {len(qids)} countries "
          f"in {total_calls} batches…")

    new_rows = []
    seen     = set()

    for i, batch in enumerate(batches):
        try:
            bindings = sparql_query(batch)
            for b in bindings:
                qid   = b["item"]["value"].split("/")[-1]
                c_qid = b["country"]["value"].split("/")[-1]
                if qid not in existing and qid not in seen:
                    new_rows.append({
                        "wikidata_id":        qid,
                        "name":               b.get("itemLabel", {}).get("value", ""),
                        "entity_type":        "province",
                        "parent_wikidata_id": c_qid,
                        "parent_name":        name_map.get(c_qid, ""),
                        "lat":                b.get("lat", {}).get("value", ""),
                        "lon":                b.get("lon", {}).get("value", ""),
                    })
                    seen.add(qid)
        except Exception as exc:
            print(f"\n  batch {i+1}/{total_calls}: {exc}")
        if i < total_calls - 1:
            time.sleep(1)
        print(f"  [{i+1}/{total_calls}] → {len(new_rows)} total", end="\r")

    print()
    with OUTPUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerows(new_rows)

    print(f"provinces: {len(new_rows)} rows appended → {OUTPUT}")


if __name__ == "__main__":
    run()
