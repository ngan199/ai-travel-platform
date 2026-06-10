"""
Extract visa / practical entry information from wikivoyage_sections JSONB.
Source: destinations.wikivoyage_sections.practical_notes
Scope: entity_type = 'country', practical_notes IS NOT NULL

Wikidata does not store visa requirements as a direct property on country items —
they are buried in free-text "visa requirements" article items with no reliable
SPARQL access. The wikivoyage practical_notes section is the closest structured
text source already in our DB. NLP extraction of structured fields
(visa_required, visa_on_arrival, duration) happens in Part 2.

Output: data/sources/practical_info/visa_notes.csv
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/practical_info/visa_notes.csv"
FIELDNAMES = [
    "wikidata_id",
    "destination_name",
    "practical_notes_text",
    "mentions_visa",
    "mentions_visa_on_arrival",
    "mentions_visa_free",
]

VISA_PATTERN = re.compile(r"\bvisa\b", re.IGNORECASE)
VISA_ON_ARRIVAL_PATTERN = re.compile(r"\bvisa[- ]on[- ]arrival\b", re.IGNORECASE)
VISA_FREE_PATTERN = re.compile(r"\bvisa[- ]free\b|\bno visa\b|\bwithout a? visa\b", re.IGNORECASE)


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                wikidata_id,
                name,
                wikivoyage_sections->>'practical_notes' AS practical_notes
            FROM destinations
            WHERE entity_type = 'country'
              AND wikivoyage_sections IS NOT NULL
              AND wikivoyage_sections->>'practical_notes' IS NOT NULL
              AND wikivoyage_sections->>'practical_notes' != ''
            ORDER BY name
        """))

        for wikidata_id, name, notes in result:
            text_val = notes.strip()
            rows.append({
                "wikidata_id": wikidata_id,
                "destination_name": name,
                "practical_notes_text": text_val,
                "mentions_visa": bool(VISA_PATTERN.search(text_val)),
                "mentions_visa_on_arrival": bool(VISA_ON_ARRIVAL_PATTERN.search(text_val)),
                "mentions_visa_free": bool(VISA_FREE_PATTERN.search(text_val)),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"visa_notes: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
