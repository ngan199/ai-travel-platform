"""
Extract language data from rest_countries JSONB column.
Source: destinations.rest_countries.languages (list of strings)
Scope: entity_type = 'country', rest_countries IS NOT NULL
Output: data/sources/language/rest_countries.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/language/rest_countries.csv"
FIELDNAMES = ["wikidata_id", "destination_name", "language_name", "is_official_language"]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT wikidata_id, name, rest_countries->'languages' AS languages
            FROM destinations
            WHERE entity_type = 'country'
              AND rest_countries IS NOT NULL
              AND rest_countries->'languages' IS NOT NULL
            ORDER BY name
        """))

        for wikidata_id, name, languages in result:
            if not isinstance(languages, list):
                continue
            for lang in languages:
                if lang:
                    rows.append({
                        "wikidata_id": wikidata_id,
                        "destination_name": name,
                        "language_name": lang.strip(),
                        "is_official_language": True,
                    })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"language: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
