"""
Extract transport text from wikivoyage_sections JSONB column.
Source: destinations.wikivoyage_sections.{get_in, get_around}
Scope: all destinations where at least one section is non-empty
Output: data/sources/transport/wikivoyage.csv
One row per (destination, section_type). Raw text preserved for Part 2 NLP.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/transport/wikivoyage.csv"
FIELDNAMES = ["wikidata_id", "destination_name", "section_type", "section_text"]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                wikidata_id,
                name,
                wikivoyage_sections->>'get_in'      AS get_in_text,
                wikivoyage_sections->>'get_around'  AS get_around_text
            FROM destinations
            WHERE wikivoyage_sections IS NOT NULL
              AND (
                (wikivoyage_sections->>'get_in'     IS NOT NULL AND wikivoyage_sections->>'get_in'     != '')
                OR
                (wikivoyage_sections->>'get_around' IS NOT NULL AND wikivoyage_sections->>'get_around' != '')
              )
            ORDER BY name
        """))

        for wikidata_id, name, get_in, get_around in result:
            if get_in and get_in.strip():
                rows.append({
                    "wikidata_id": wikidata_id,
                    "destination_name": name,
                    "section_type": "get_in",
                    "section_text": get_in.strip(),
                })
            if get_around and get_around.strip():
                rows.append({
                    "wikidata_id": wikidata_id,
                    "destination_name": name,
                    "section_type": "get_around",
                    "section_text": get_around.strip(),
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wikivoyage_transport: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
