"""
Splink Prediction Visualisation — 6 structured tables.

For each table produces two interactive dashboards:
  1. comparison_viewer  — browse individual record pairs + their comparison vectors
  2. cluster_studio     — browse resolved clusters (10 sample clusters per table)

Outputs:
  data/splink_outputs/visualise/<table>_comparison_viewer.html
  data/splink_outputs/visualise/<table>_cluster_studio.html
"""
from pathlib import Path
import json
import pandas as pd
from splink import Linker, DuckDBAPI

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized/splink_input"
MODEL_DIR  = ROOT / "data/splink_outputs/training"
OUTPUT_DIR = ROOT / "data/splink_outputs/visualise"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NUMERIC_COLS = {"lat", "lon", "star_rating", "rooms"}
THRESHOLD    = 0.8


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


def run_table(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}")
    print(f"{'='*60}")

    df = load(name)
    model = json.loads((MODEL_DIR / f"{name}_model.json").read_text())
    model["retain_intermediate_calculation_columns"] = True
    linker = Linker(df, model, db_api=DuckDBAPI())

    print("  [1/3] Predicting…")
    df_pred = linker.inference.predict(threshold_match_probability=THRESHOLD)

    print("  [2/3] Clustering…")
    df_clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(
        df_pred, threshold_match_probability=THRESHOLD
    )

    print("  [3/3] Saving dashboards…")

    comp_path = str(OUTPUT_DIR / f"{name}_comparison_viewer.html")
    linker.visualisations.comparison_viewer_dashboard(
        df_pred,
        out_path=comp_path,
        overwrite=True,
        num_example_rows=10,
    )
    inject_title(Path(comp_path), f"{name} — Comparison Viewer")

    cluster_path = str(OUTPUT_DIR / f"{name}_cluster_studio.html")
    linker.visualisations.cluster_studio_dashboard(
        df_pred,
        df_clusters,
        out_path=cluster_path,
        sample_size=10,
        overwrite=True,
    )
    inject_title(Path(cluster_path), f"{name} — Cluster Studio")

    print(f"  comparison viewer → {Path(comp_path).relative_to(ROOT)}")
    print(f"  cluster studio    → {Path(cluster_path).relative_to(ROOT)}")


if __name__ == "__main__":
    print("=== Splink Visualisation — 6 tables ===")
    for table in ["destinations", "venues", "accommodations", "transport_hubs", "festivals", "activities"]:
        run_table(table)
    print(f"\n=== Done — dashboards in {OUTPUT_DIR.relative_to(ROOT)} ===")
