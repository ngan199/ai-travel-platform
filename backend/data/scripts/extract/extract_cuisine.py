"""
Extract cuisine text from wikivoyage_sections JSONB column.
Source: destinations.wikivoyage_sections.eat_overview
Scope: all destinations where wikivoyage_sections.eat_overview IS NOT NULL
Output: data/sources/cuisine/wikivoyage.csv

street_food_available is derived by keyword detection on the eat_overview text.
The raw text is preserved for NLP extraction in Part 2.
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/cuisine/wikivoyage.csv"
FIELDNAMES = [
    "wikidata_id",
    "destination_name",
    "eat_section_text",
    "street_food_available",
]

STREET_FOOD_PATTERNS = re.compile(
    r"\b(street food|street-food|hawker|night market|food stall|food cart|food vendor"
    r"|pavement food|roadside food|outdoor market|wet market)\b",
    re.IGNORECASE,
)


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT wikidata_id, name, wikivoyage_sections->>'eat_overview' AS eat
            FROM destinations
            WHERE wikivoyage_sections IS NOT NULL
              AND wikivoyage_sections->>'eat_overview' IS NOT NULL
              AND wikivoyage_sections->>'eat_overview' != ''
            ORDER BY name
        """))

        for wikidata_id, name, eat in result:
            street_food = bool(STREET_FOOD_PATTERNS.search(eat))
            rows.append({
                "wikidata_id": wikidata_id,
                "destination_name": name,
                "eat_section_text": eat.strip(),
                "street_food_available": street_food,
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"cuisine: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
