"""
Extract safety tip text from wikivoyage_sections JSONB column.
Source: destinations.wikivoyage_sections.stay_safe
Scope: all destinations where stay_safe is non-empty
Output: data/sources/safety_tip/wikivoyage.csv

Raw text is preserved for NLP extraction in Part 2.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/safety_tip/wikivoyage.csv"
FIELDNAMES = ["wikidata_id", "destination_name", "stay_safe_text"]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT wikidata_id, name, wikivoyage_sections->>'stay_safe' AS stay_safe
            FROM destinations
            WHERE wikivoyage_sections IS NOT NULL
              AND wikivoyage_sections->>'stay_safe' IS NOT NULL
              AND wikivoyage_sections->>'stay_safe' != ''
            ORDER BY name
        """))

        for wikidata_id, name, stay_safe in result:
            rows.append({
                "wikidata_id": wikidata_id,
                "destination_name": name,
                "stay_safe_text": stay_safe.strip(),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"safety_tip: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
