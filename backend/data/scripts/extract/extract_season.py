"""
Derive season records from climate JSONB column.
Source: destinations.climate.{best_months, worst_months, rainy_season,
        monthly_avg_temp, monthly_avg_precipitation}
Scope: all destinations where climate IS NOT NULL
Output: data/sources/season/from_climate.csv

Season derivation logic:
  best_months   → season_type = high
  rainy_season  → season_type = rainy
  worst_months  → season_type = low
  remaining     → season_type = shoulder
  A month in multiple lists → priority: rainy > high > low > shoulder
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from app.db.database import engine
from sqlalchemy import text

OUTPUT = Path(__file__).parents[3] / "data/sources/season/from_climate.csv"
FIELDNAMES = [
    "wikidata_id",
    "destination_name",
    "season_type",
    "month_numbers",
    "avg_temp_celsius",
    "avg_rainfall_mm",
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

PRIORITY = {"rainy": 0, "high": 1, "low": 2, "shoulder": 3}


def _safe_avg(values, indices):
    """Return mean of values[i] for i in indices (1-based), skipping None."""
    nums = [values[i - 1] for i in indices if values[i - 1] is not None]
    return round(sum(nums) / len(nums), 1) if nums else None


def _classify_months(climate: dict) -> dict[int, str]:
    best = set(climate.get("best_months") or [])
    rainy = set(climate.get("rainy_season") or [])
    worst = set(climate.get("worst_months") or [])
    all_months = set(range(1, 13))

    classification: dict[int, str] = {}
    for m in all_months:
        candidates = []
        if m in rainy:
            candidates.append("rainy")
        if m in best:
            candidates.append("high")
        if m in worst:
            candidates.append("low")
        if not candidates:
            candidates.append("shoulder")
        classification[m] = min(candidates, key=lambda t: PRIORITY[t])
    return classification


def _group_by_season(classification: dict[int, str]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for month, season in classification.items():
        groups.setdefault(season, []).append(month)
    return groups


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
            if len(temps) < 12:
                temps = temps + [None] * (12 - len(temps))
            if len(precip) < 12:
                precip = precip + [None] * (12 - len(precip))

            classification = _classify_months(climate)
            groups = _group_by_season(classification)

            for season_type, months in sorted(groups.items(), key=lambda x: x[1][0]):
                rows.append({
                    "wikidata_id": wikidata_id,
                    "destination_name": name,
                    "season_type": season_type,
                    "month_numbers": json.dumps(sorted(months)),
                    "avg_temp_celsius": _safe_avg(temps, months),
                    "avg_rainfall_mm": _safe_avg(precip, months),
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"season: {len(rows)} rows → {OUTPUT}")


if __name__ == "__main__":
    run()
