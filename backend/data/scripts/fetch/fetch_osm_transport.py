"""
Fetch transport hub POIs from OSM Overpass API for each destination.
Covers: airports, ports, bus stations, train stations, ferry terminals.
Bounding box: ±0.5° for cities, ±2° for countries/regions.
Rate limit: 2 s between requests.
Output: data/sources/transport/osm_hubs.csv
"""
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/transport/osm_hubs.csv"
FIELDNAMES = [
    "destination_wikidata_id", "destination_name",
    "osm_id", "osm_type",
    "hub_name", "hub_type",
    "iata_code", "icao_code",
    "lat", "lon",
]

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {
    "User-Agent": "travel-ai-platform/1.0 (data-pipeline; contact: trankimngan.dev@gmail.com)",
}
RETRY_BACKOFF = [5, 15, 30]

CITY_TYPES = {"city", "district", "neighborhood"}
COUNTRY_RADIUS = 2.0
CITY_RADIUS = 0.5

TAGS = """
  node["aeroway"="aerodrome"];
  node["amenity"="ferry_terminal"];
  node["amenity"="bus_station"];
  node["railway"="station"];
  node["public_transport"="station"];
  way["aeroway"="aerodrome"];
  way["amenity"="ferry_terminal"];
  way["amenity"="bus_station"];
  way["railway"="station"];
  relation["aeroway"="aerodrome"];
  relation["amenity"="ferry_terminal"];
"""


def build_query(lat: float, lon: float, radius: float) -> str:
    s, n = lat - radius, lat + radius
    w, e = lon - radius, lon + radius
    bbox = f"{s},{w},{n},{e}"
    tag_lines = "\n".join(
        f'  {line.strip().rstrip(";")};' for line in TAGS.strip().splitlines()
        if line.strip()
    )
    return f"""
[out:json][timeout:30][bbox:{bbox}];
(
{tag_lines}
);
out center 300;
"""


def classify_hub(tags: dict) -> str:
    aeroway = tags.get("aeroway", "")
    amenity = tags.get("amenity", "")
    railway = tags.get("railway", "")
    pt = tags.get("public_transport", "")
    if aeroway == "aerodrome":
        return "airport"
    if amenity == "ferry_terminal":
        return "port"
    if amenity == "bus_station":
        return "bus_station"
    if railway in ("station", "halt"):
        return "train_station"
    if pt == "station":
        return "station"
    return "transport_hub"


def fetch_hubs(lat: float, lon: float, radius: float) -> list[dict]:
    query = build_query(lat, lon, radius)
    last_exc = None
    for attempt, mirror in enumerate(OVERPASS_MIRRORS * 2):
        try:
            resp = requests.post(mirror, data={"data": query}, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            break
        except Exception as exc:
            last_exc = exc
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            time.sleep(wait)
    else:
        raise last_exc
    elements = resp.json().get("elements", [])
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en", "")
        if not name:
            continue
        if el["type"] == "node":
            lat_v, lon_v = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat_v, lon_v = center.get("lat"), center.get("lon")
        rows.append({
            "osm_id": el["id"],
            "osm_type": el["type"],
            "hub_name": name,
            "hub_type": classify_hub(tags),
            "iata_code": tags.get("iata", ""),
            "icao_code": tags.get("icao", ""),
            "lat": lat_v,
            "lon": lon_v,
        })
    return rows


def load_destinations():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT wikidata_id, name, entity_type, lat, lon
            FROM destinations
            WHERE lat IS NOT NULL AND lon IS NOT NULL
            ORDER BY entity_type, name
        """))
        return list(result)


def run():
    destinations = load_destinations()
    all_rows = []
    total = len(destinations)

    print(f"Fetching OSM transport hubs for {total} destinations…")

    for i, (wikidata_id, name, entity_type, lat, lon) in enumerate(destinations):
        radius = CITY_RADIUS if entity_type in CITY_TYPES else COUNTRY_RADIUS
        try:
            hubs = fetch_hubs(lat, lon, radius)
            for h in hubs:
                h["destination_wikidata_id"] = wikidata_id
                h["destination_name"] = name
                all_rows.append({k: h.get(k, "") for k in FIELDNAMES})
        except Exception as exc:
            print(f"  [{i+1}/{total}] {name}: {exc}")
        if i < total - 1:
            time.sleep(2)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{total} done, {len(all_rows)} hubs so far")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"osm_transport: {len(all_rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
