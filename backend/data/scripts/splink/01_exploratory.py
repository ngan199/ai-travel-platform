"""
Splink Exploratory Analysis — structured tables only (9 tables).
Knowledge/content tables (free text) are excluded.

For each table:
  1. completeness_chart  → HTML (null rates per column)
  2. profile_columns     → HTML (value distributions for key columns)
  3. terminal summary    → row count, completeness %, top-5 values per profiled column

Outputs: data/splink_outputs/exploratory/<table>_completeness.html
                                         <table>_profile.html
"""
from pathlib import Path
import pandas as pd
from splink import DuckDBAPI
from splink.exploratory import completeness_chart, profile_columns

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized"
OUTPUT_DIR = ROOT / "data/splink_outputs/exploratory"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

db_api = DuckDBAPI()

# ── Splink entity-resolution targets ────────────────────────────────────────
SPLINK_TABLES = {
    "destinations": {
        "path":         NORM / "splink_input/destinations.csv",
        "profile_cols": ["name_clean", "entity_type", "lat", "lon"],
    },
    "venues": {
        "path":         NORM / "splink_input/venues.csv",
        "profile_cols": ["name_clean", "entity_type", "lat", "lon", "source"],
    },
    "accommodations": {
        "path":         NORM / "splink_input/accommodations.csv",
        "profile_cols": ["name_clean", "entity_type", "lat", "lon", "star_rating", "rooms", "source"],
    },
    "transport_hubs": {
        "path":         NORM / "splink_input/transport_hubs.csv",
        "profile_cols": ["name_clean", "entity_type", "lat", "lon", "iata_code", "source"],
    },
    "festivals": {
        "path":         NORM / "splink_input/festivals.csv",
        "profile_cols": ["name_clean", "festival_type", "destination_id", "start_date"],
    },
    "activities": {
        "path":         NORM / "splink_input/activities.csv",
        "profile_cols": ["name_clean", "activity_type", "destination_id", "lat", "lon"],
    },
}

# ── Reference / lookup tables ────────────────────────────────────────────────
REFERENCE_TABLES = {
    "languages": {
        "path":         NORM / "languages.csv",
        "profile_cols": ["language_name", "is_official_language"],
    },
    "currencies": {
        "path":         NORM / "currencies.csv",
        "profile_cols": ["currency_code", "currency_name"],
    },
    "seasons": {
        "path":         NORM / "seasons.csv",
        "profile_cols": ["season_type", "avg_temp_celsius", "avg_rainfall_mm"],
    },
    "months": {
        "path":         NORM / "months.csv",
        "profile_cols": ["month_name", "avg_temp_celsius", "avg_rainfall_mm", "avg_humidity"],
    },
}

NUMERIC_COLS = {"lat", "lon", "star_rating", "rooms", "avg_temp_celsius", "avg_rainfall_mm", "avg_humidity"}


def summarise(name: str, df: pd.DataFrame, profile_cols: list) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}  ({len(df):,} rows)")
    print(f"{'='*60}")

    skip = {"unique_id", "source", "source_id", "festival_id",
            "section_text", "eat_section_text", "respect_text",
            "local_laws_text", "stay_safe_text", "practical_notes_text"}
    check_cols = [c for c in df.columns if c not in skip]
    null_pct = (df[check_cols].isnull().sum() / len(df) * 100).round(1)

    print("  Completeness:")
    for col in check_cols:
        flag = "  ← high nulls" if null_pct[col] > 50 else ""
        print(f"    {col:<26s}  {100 - null_pct[col]:5.1f}% complete{flag}")

    print("\n  Top-5 values per profiled column:")
    for col in profile_cols:
        if col not in df.columns:
            continue
        if col in NUMERIC_COLS:
            non_null = df[col].dropna()
            if len(non_null):
                print(f"    {col:<26s}  min={non_null.min():.2f}  "
                      f"max={non_null.max():.2f}  "
                      f"null={df[col].isna().sum():,}")
        else:
            top  = df[col].value_counts().head(5)
            vals = "  |  ".join(f"{v!r}: {n:,}" for v, n in top.items())
            print(f"    {col:<26s}  {vals}")


def inject_title(path: Path, title: str) -> None:
    """Inject <title> and a visible <h1> banner into a saved Altair HTML file."""
    html = path.read_text(encoding="utf-8")
    html = html.replace(
        "<head>",
        f"<head>\n  <title>{title}</title>",
        1,
    )
    html = html.replace(
        "<body>",
        (
            "<body>\n"
            f'  <div style="font-family:sans-serif;padding:12px 20px;'
            f'background:#1e3a5f;color:#fff;font-size:18px;font-weight:bold;">'
            f"{title}</div>"
        ),
        1,
    )
    path.write_text(html, encoding="utf-8")


def run_table(name: str, cfg: dict) -> None:
    df = pd.read_csv(cfg["path"], dtype=str, low_memory=False)

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    summarise(name, df, cfg["profile_cols"])

    comp_path = OUTPUT_DIR / f"{name}_completeness.html"
    completeness_chart(df, db_api=db_api).save(str(comp_path))
    inject_title(comp_path, f"{name} — Completeness")
    print(f"\n  completeness → {comp_path.relative_to(ROOT)}")

    prof_path = OUTPUT_DIR / f"{name}_profile.html"
    profile_columns(
        df, db_api=db_api, top_n=10, bottom_n=5,
        column_expressions=cfg["profile_cols"],
    ).save(str(prof_path))
    inject_title(prof_path, f"{name} — Profile")
    print(f"  profile      → {prof_path.relative_to(ROOT)}")


if __name__ == "__main__":
    print("=== Splink Exploratory Analysis — 9 structured tables ===\n")

    print("── Splink entity-resolution targets ─────────────────────")
    for name, cfg in SPLINK_TABLES.items():
        run_table(name, cfg)

    print("\n── Reference / lookup tables ─────────────────────────────")
    for name, cfg in REFERENCE_TABLES.items():
        run_table(name, cfg)

    print(f"\n=== Done — charts in {OUTPUT_DIR.relative_to(ROOT)} ===")
