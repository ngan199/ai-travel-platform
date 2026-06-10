"""
Extract currency data from rest_countries JSONB column.
Source: destinations.rest_countries.{currency_code, currency_name}
Scope: entity_type = 'country', rest_countries IS NOT NULL
Output: data/sources/currency/rest_countries.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/currency/rest_countries.csv"
FIELDNAMES = ["wikidata_id", "destination_name", "currency_code", "currency_name"]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                wikidata_id,
                name,
                rest_countries->>'currency_code' AS currency_code,
                rest_countries->>'currency_name' AS currency_name
            FROM destinations
            WHERE entity_type = 'country'
              AND rest_countries IS NOT NULL
              AND rest_countries->>'currency_code' IS NOT NULL
            ORDER BY name
        """))

        for wikidata_id, name, currency_code, currency_name in result:
            rows.append({
                "wikidata_id": wikidata_id,
                "destination_name": name,
                "currency_code": (currency_code or "").strip(),
                "currency_name": (currency_name or "").strip(),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"currency: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
