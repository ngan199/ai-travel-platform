"""
Fetch accommodation POIs from OSM Overpass API for each destination.
Covers: hotels, hostels, guesthouses, motels, resorts, campsites.
Bounding box: ±0.5° for cities, ±2° for countries/regions.
Rate limit: 2 s between requests.
Output: data/sources/accommodation/osm.csv
"""
import csv
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/accommodation/osm.csv"
FIELDNAMES = [
    "destination_wikidata_id", "destination_name",
    "osm_id", "osm_type",
    "accommodation_name", "accommodation_type",
    "star_rating", "rooms",
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

ACCOMMODATION_TOURISM_VALUES = {
    "hotel", "hostel", "guest_house", "motel",
    "resort", "apartment", "chalet", "camp_site",
}


def build_query(lat: float, lon: float, radius: float) -> str:
    s, n = lat - radius, lat + radius
    w, e = lon - radius, lon + radius
    bbox = f"{s},{w},{n},{e}"
    tag_clauses = "\n".join(
        f'  node["tourism"="{v}"];'
        for v in ACCOMMODATION_TOURISM_VALUES
    ) + "\n" + "\n".join(
        f'  way["tourism"="{v}"];'
        for v in ACCOMMODATION_TOURISM_VALUES
    )
    return f"""
[out:json][timeout:30][bbox:{bbox}];
(
{tag_clauses}
);
out center 500;
"""


def fetch_accommodation(lat: float, lon: float, radius: float) -> list[dict]:
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
            "accommodation_name": name,
            "accommodation_type": tags.get("tourism", ""),
            "star_rating": tags.get("stars", ""),
            "rooms": tags.get("rooms", ""),
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

    print(f"Fetching OSM accommodation for {total} destinations…")

    for i, (wikidata_id, name, entity_type, lat, lon) in enumerate(destinations):
        radius = CITY_RADIUS if entity_type in CITY_TYPES else COUNTRY_RADIUS
        try:
            items = fetch_accommodation(lat, lon, radius)
            for item in items:
                item["destination_wikidata_id"] = wikidata_id
                item["destination_name"] = name
                all_rows.append({k: item.get(k, "") for k in FIELDNAMES})
        except Exception as exc:
            print(f"  [{i+1}/{total}] {name}: {exc}")
        if i < total - 1:
            time.sleep(2)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{total} done, {len(all_rows)} items so far")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"osm_accommodation: {len(all_rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
