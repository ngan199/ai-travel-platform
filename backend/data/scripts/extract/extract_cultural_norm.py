"""
Extract cultural norm and local law text from wikivoyage_sections JSONB column.
Source: destinations.wikivoyage_sections.{respect, local_laws}
Scope: all destinations where at least one of those keys is non-empty
Output: data/sources/cultural_norm/wikivoyage.csv

Raw text is preserved for NLP extraction in Part 2.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/cultural_norm/wikivoyage.csv"
FIELDNAMES = [
    "wikidata_id",
    "destination_name",
    "respect_text",
    "local_laws_text",
]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                wikidata_id,
                name,
                wikivoyage_sections->>'respect'    AS respect,
                wikivoyage_sections->>'local_laws' AS local_laws
            FROM destinations
            WHERE wikivoyage_sections IS NOT NULL
              AND (
                (wikivoyage_sections->>'respect' IS NOT NULL AND wikivoyage_sections->>'respect' != '')
                OR
                (wikivoyage_sections->>'local_laws' IS NOT NULL AND wikivoyage_sections->>'local_laws' != '')
              )
            ORDER BY name
        """))

        for wikidata_id, name, respect, local_laws in result:
            rows.append({
                "wikidata_id": wikidata_id,
                "destination_name": name,
                "respect_text": (respect or "").strip(),
                "local_laws_text": (local_laws or "").strip(),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"cultural_norm: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
