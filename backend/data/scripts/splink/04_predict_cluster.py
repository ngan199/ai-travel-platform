"""
Splink Prediction & Clustering — 6 structured tables.

For each table:
  1. Load trained model from JSON
  2. Run predict (threshold = 0.8)
  3. Run clustering (threshold = 0.8)
  4. Save cluster assignments → data/normalized/splink_input/<table>_clustered.csv

Output adds a `cluster_id` column to each table.
Records with the same cluster_id are resolved as the same entity.
"""
from pathlib import Path
import json
import pandas as pd
from splink import Linker, DuckDBAPI

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized/splink_input"
MODEL_DIR  = ROOT / "data/splink_outputs/training"
OUTPUT_DIR = NORM  # write clustered files alongside inputs

NUMERIC_COLS = {"lat", "lon", "star_rating", "rooms"}
THRESHOLD    = 0.8


def load(name: str) -> pd.DataFrame:
    path = NORM / f"{name}.csv"
    df = pd.read_csv(path, dtype=str, low_memory=False)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def run_table(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}")
    print(f"{'='*60}")

    df = load(name)
    model = json.loads((MODEL_DIR / f"{name}_model.json").read_text())

    linker = Linker(df, model, db_api=DuckDBAPI())

    print(f"  [1/2] Predicting (threshold={THRESHOLD})…")
    df_pred = linker.inference.predict(threshold_match_probability=THRESHOLD)

    print(f"  [2/2] Clustering…")
    df_clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
        df_pred, threshold_match_probability=THRESHOLD
    )

    result = df_clusters.as_pandas_dataframe()
    out_path = OUTPUT_DIR / f"{name}_clustered.csv"
    result.to_csv(out_path, index=False)

    n_clusters   = result["cluster_id"].nunique()
    n_singletons = (result.groupby("cluster_id").size() == 1).sum()
    n_merged     = n_clusters - n_singletons

    print(f"  rows      : {len(result):,}")
    print(f"  clusters  : {n_clusters:,}  ({n_merged:,} multi-record, {n_singletons:,} singletons)")
    print(f"  → {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    print("=== Splink Prediction & Clustering — 6 tables ===")
    for table in ["destinations", "venues", "accommodations", "transport_hubs", "festivals", "activities"]:
        run_table(table)
    print(f"\n=== Done — clustered files in {NORM.relative_to(ROOT)} ===")
