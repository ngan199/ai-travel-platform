"""
Extract per-month weather records from climate JSONB column.
Source: destinations.climate.{monthly_avg_temp, monthly_avg_precipitation, monthly_avg_humidity}
Scope: all destinations where climate IS NOT NULL
Output: data/sources/season/month_weather.csv
One row per (destination, month) — up to 788 × 12 = 9,456 rows.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/season/month_weather.csv"
FIELDNAMES = [
    "wikidata_id",
    "destination_name",
    "month_number",
    "month_name",
    "avg_temp_celsius",
    "avg_rainfall_mm",
    "avg_humidity",
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def run():
    rows = []

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT wikidata_id, name, climate
            FROM destinations
            WHERE climate IS NOT NULL
            ORDER BY name
        """))

        for wikidata_id, name, climate in result:
            temps = climate.get("monthly_avg_temp") or []
            precip = climate.get("monthly_avg_precipitation") or []
            humidity = climate.get("monthly_avg_humidity") or []

            for i in range(12):
                rows.append({
                    "wikidata_id": wikidata_id,
                    "destination_name": name,
                    "month_number": i + 1,
                    "month_name": MONTH_NAMES[i],
                    "avg_temp_celsius": temps[i] if i < len(temps) else None,
                    "avg_rainfall_mm": precip[i] if i < len(precip) else None,
                    "avg_humidity": humidity[i] if i < len(humidity) else None,
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"month_weather: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
