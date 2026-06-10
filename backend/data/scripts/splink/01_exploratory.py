"""
Splink Step 1 — Exploratory Analysis
Runs completeness_chart and profile_columns on all 3 Splink input tables.
Outputs HTML charts to data/splink_outputs/exploratory/
"""
from pathlib import Path
import pandas as pd
from splink import DuckDBAPI
from splink.exploratory import completeness_chart, profile_columns

ROOT = Path(__file__).parents[3]
INPUT_DIR = ROOT / "data/normalized/splink_input"
OUTPUT_DIR = ROOT / "data/splink_outputs/exploratory"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

db_api = DuckDBAPI()

TABLES = {
    "venues": {
        "path": INPUT_DIR / "venues.csv",
        "profile_cols": ["name_clean", "entity_type", "destination_name"],
    },
    "transport_hubs": {
        "path": INPUT_DIR / "transport_hubs.csv",
        "profile_cols": ["name_clean", "entity_type", "iata_code"],
    },
    "accommodations": {
        "path": INPUT_DIR / "accommodations.csv",
        "profile_cols": ["name_clean", "entity_type", "star_rating"],
    },
}


def summarise(name: str, df: pd.DataFrame) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}  ({len(df):,} rows)")
    print(f"{'='*60}")
    print(f"  Columns : {list(df.columns)}")
    print()

    null_cols = [c for c in df.columns if c not in ("unique_id", "source", "source_id")]
    null_counts = df[null_cols].isnull().sum()
    null_pct = (null_counts / len(df) * 100).round(1)
    print("  Null counts (matching-relevant columns):")
    for col in null_cols:
        bar = "#" * int(null_pct[col] / 2)
        print(f"    {col:<20s}  {null_counts[col]:>6,}  ({null_pct[col]:5.1f}%)  {bar}")


def run_table(name: str, cfg: dict) -> None:
    df = pd.read_csv(cfg["path"], dtype=str)

    # Re-parse numeric columns so Splink sees correct types
    for col in ("lat", "lon", "star_rating"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    summarise(name, df)

    # Completeness chart
    comp_path = OUTPUT_DIR / f"{name}_completeness.html"
    fig = completeness_chart(df, db_api=db_api)
    fig.save(str(comp_path))
    print(f"  completeness chart → {comp_path.relative_to(ROOT)}")

    # Profile columns
    prof_path = OUTPUT_DIR / f"{name}_profile.html"
    fig2 = profile_columns(df, db_api=db_api, top_n=10, bottom_n=5,
                            column_expressions=cfg["profile_cols"])
    fig2.save(str(prof_path))
    print(f"  profile chart      → {prof_path.relative_to(ROOT)}")


if __name__ == "__main__":
    print("=== Splink Exploratory Analysis ===")
    for table_name, config in TABLES.items():
        run_table(table_name, config)
    print(f"\n=== Done — charts saved to {OUTPUT_DIR.relative_to(ROOT)} ===")
