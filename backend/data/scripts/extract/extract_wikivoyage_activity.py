"""
Extract activity text from wikivoyage_sections JSONB column.
Source: destinations.wikivoyage_sections.{do, see}
Scope: all destinations where at least one section is non-empty
Output: data/sources/activity/wikivoyage.csv
One row per (destination, section_type). Raw text preserved for Part 2 NLP.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/activity/wikivoyage.csv"
FIELDNAMES = ["wikidata_id", "destination_name", "section_type", "section_text"]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                wikidata_id,
                name,
                wikivoyage_sections->>'do'  AS do_text,
                wikivoyage_sections->>'see' AS see_text
            FROM destinations
            WHERE wikivoyage_sections IS NOT NULL
              AND (
                (wikivoyage_sections->>'do'  IS NOT NULL AND wikivoyage_sections->>'do'  != '')
                OR
                (wikivoyage_sections->>'see' IS NOT NULL AND wikivoyage_sections->>'see' != '')
              )
            ORDER BY name
        """))

        for wikidata_id, name, do_text, see_text in result:
            if do_text and do_text.strip():
                rows.append({
                    "wikidata_id": wikidata_id,
                    "destination_name": name,
                    "section_type": "do",
                    "section_text": do_text.strip(),
                })
            if see_text and see_text.strip():
                rows.append({
                    "wikidata_id": wikidata_id,
                    "destination_name": name,
                    "section_type": "see",
                    "section_text": see_text.strip(),
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wikivoyage_activity: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
