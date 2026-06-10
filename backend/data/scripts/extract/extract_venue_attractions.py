"""
Extract venue records from top_attractions JSONB column.
Source: destinations.top_attractions (array of {name, wikidata, category})
Scope: all destinations where top_attractions IS NOT NULL
Output: data/sources/venue/top_attractions.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/venue/top_attractions.csv"
FIELDNAMES = [
    "destination_wikidata_id",
    "destination_name",
    "venue_name",
    "venue_wikidata_id",
    "venue_category",
]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT wikidata_id, name, top_attractions
            FROM destinations
            WHERE top_attractions IS NOT NULL
            ORDER BY name
        """))

        for wikidata_id, dest_name, attractions in result:
            if not isinstance(attractions, list):
                continue
            for item in attractions:
                if not isinstance(item, dict):
                    continue
                venue_name = item.get("name", "").strip()
                if not venue_name:
                    continue
                rows.append({
                    "destination_wikidata_id": wikidata_id,
                    "destination_name": dest_name,
                    "venue_name": venue_name,
                    "venue_wikidata_id": item.get("wikidata", ""),
                    "venue_category": item.get("category", ""),
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"venue_attractions: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
