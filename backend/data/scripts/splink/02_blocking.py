"""
Splink Blocking Analysis — 6 structured tables.

For each table:
  - Define 2-3 blocking rules using block_on()
  - Count candidate pairs per rule
  - Save cumulative comparisons chart → HTML
  - Print summary: rows, rules, total candidate pairs

Output: data/splink_outputs/blocking/<table>_blocking.html
"""
from pathlib import Path
import pandas as pd
from splink import block_on, Linker, DuckDBAPI
from splink.blocking_analysis import (
    count_comparisons_from_blocking_rule,
    cumulative_comparisons_to_be_scored_from_blocking_rules_chart,
)

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized/splink_input"
OUTPUT_DIR = ROOT / "data/splink_outputs/blocking"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NUMERIC_COLS = {"lat", "lon", "star_rating", "rooms"}


def load(name: str) -> pd.DataFrame:
    path = NORM / f"{name}.csv"
    df = pd.read_csv(path, dtype=str, low_memory=False)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def inject_title(path: Path, title: str) -> None:
    html = path.read_text(encoding="utf-8")
    html = html.replace("<head>", f"<head>\n  <title>{title}</title>", 1)
    html = html.replace(
        "<body>",
        "<body>\n"
        f'  <div style="font-family:sans-serif;padding:12px 20px;'
        f'background:#1e3a5f;color:#fff;font-size:18px;font-weight:bold;">'
        f"{title}</div>",
        1,
    )
    path.write_text(html, encoding="utf-8")


def analyse(name: str, df: pd.DataFrame, rules: list, unique_id_col: str = "unique_id") -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}  ({len(df):,} rows)")
    print(f"{'='*60}")

    db_api = DuckDBAPI()

    total = 0
    for rule in rules:
        result = count_comparisons_from_blocking_rule(
            table_or_tables=[df],
            blocking_rule=rule,
            link_type="dedupe_only",
            db_api=db_api,
            unique_id_column_name=unique_id_col,
        )
        count = result.get("number_of_comparisons_to_be_scored_post_filter_conditions", 0)
        sql = rule.get_blocking_rule("duckdb").blocking_rule_sql
        print(f"  {sql:<60s}  →  {count:>12,.0f} pairs")
        total += count

    print(f"  {'TOTAL (with overlap)':<60s}  →  {total:>12,.0f} pairs")

    chart_path = OUTPUT_DIR / f"{name}_blocking.html"
    cumulative_comparisons_to_be_scored_from_blocking_rules_chart(
        table_or_tables=[df],
        blocking_rules=rules,
        link_type="dedupe_only",
        db_api=db_api,
        unique_id_column_name=unique_id_col,
    ).save(str(chart_path))
    inject_title(chart_path, f"{name} — Blocking Rules")
    print(f"  chart → {chart_path.relative_to(ROOT)}")


# ── Table definitions ────────────────────────────────────────────────────────

def run_destinations():
    df = load("destinations")
    rules = [
        block_on("name_clean"),
        block_on("substr(name_clean, 1, 6)", "entity_type"),
        block_on("parent_id", "substr(name_clean, 1, 4)"),
    ]
    analyse("destinations", df, rules)


def run_venues():
    df = load("venues")
    rules = [
        block_on("name_clean"),
        block_on("destination_id", "substr(name_clean, 1, 6)"),
        block_on("round(lat, 2)", "round(lon, 2)"),
    ]
    analyse("venues", df, rules)


def run_accommodations():
    df = load("accommodations")
    rules = [
        block_on("name_clean"),
        block_on("round(lat, 2)", "round(lon, 2)"),
        block_on("destination_id", "substr(name_clean, 1, 8)"),
    ]
    analyse("accommodations", df, rules)


def run_transport_hubs():
    df = load("transport_hubs")
    rules = [
        block_on("name_clean"),
        block_on("iata_code"),
        block_on("round(lat, 2)", "round(lon, 2)", "entity_type"),
    ]
    analyse("transport_hubs", df, rules)


def run_festivals():
    df = load("festivals")
    rules = [
        block_on("name_clean"),
        block_on("destination_id", "substr(name_clean, 1, 5)"),
    ]
    analyse("festivals", df, rules)


def run_activities():
    df = load("activities")
    rules = [
        block_on("name_clean"),
        block_on("activity_type", "round(lat, 1)", "round(lon, 1)"),
        block_on("destination_id", "substr(name_clean, 1, 6)"),
    ]
    analyse("activities", df, rules)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Splink Blocking Analysis — 6 tables ===")
    run_destinations()
    run_venues()
    run_accommodations()
    run_transport_hubs()
    run_festivals()
    run_activities()
    print(f"\n=== Done — charts in {OUTPUT_DIR.relative_to(ROOT)} ===")
