"""
Fetch tourism/amenity venue POIs from OSM Overpass API for each destination.
Scope: all destinations with lat/lon populated.
Bounding box: ±0.5° for cities/districts/neighborhoods, ±2° for countries/regions.
Rate limit: 2 s between requests.
Output: data/sources/venue/osm_venues.csv
"""
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/venue/osm_venues.csv"
FIELDNAMES = [
    "destination_wikidata_id", "destination_name",
    "osm_id", "osm_type",
    "venue_name", "venue_type", "venue_subtype",
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
  node["tourism"="attraction"];
  node["tourism"="museum"];
  node["tourism"="artwork"];
  node["tourism"="gallery"];
  node["tourism"="viewpoint"];
  node["tourism"="theme_park"];
  node["amenity"="place_of_worship"];
  node["amenity"="theatre"];
  node["amenity"="cinema"];
  node["leisure"="park"];
  node["leisure"="nature_reserve"];
  node["historic"="monument"];
  node["historic"="castle"];
  node["historic"="ruins"];
  way["tourism"="attraction"];
  way["tourism"="museum"];
  way["amenity"="place_of_worship"];
  way["leisure"="park"];
  way["historic"="monument"];
  way["historic"="castle"];
  relation["tourism"="attraction"];
  relation["leisure"="park"];
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
out center 500;
"""


def fetch_venues(lat: float, lon: float, radius: float) -> list[dict]:
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
        venue_type = (
            tags.get("tourism") or tags.get("amenity") or
            tags.get("leisure") or tags.get("historic") or ""
        )
        if el["type"] == "node":
            lat_v, lon_v = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat_v, lon_v = center.get("lat"), center.get("lon")
        rows.append({
            "osm_id": el["id"],
            "osm_type": el["type"],
            "venue_name": name,
            "venue_type": venue_type,
            "venue_subtype": tags.get("historic", ""),
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

    print(f"Fetching OSM venues for {total} destinations…")

    for i, (wikidata_id, name, entity_type, lat, lon) in enumerate(destinations):
        radius = CITY_RADIUS if entity_type in CITY_TYPES else COUNTRY_RADIUS
        try:
            venues = fetch_venues(lat, lon, radius)
            for v in venues:
                v["destination_wikidata_id"] = wikidata_id
                v["destination_name"] = name
                all_rows.append({k: v.get(k, "") for k in FIELDNAMES})
        except Exception as exc:
            print(f"  [{i+1}/{total}] {name}: {exc}")
        if i < total - 1:
            time.sleep(2)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{total} done, {len(all_rows)} venues so far")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"osm_venues: {len(all_rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
