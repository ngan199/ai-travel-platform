"""
Splink Evaluation — 6 structured tables.

Pseudo-labels created deterministically (no manual ground truth):
  - tables with coords: name_clean + round(lat,2) + round(lon,2)
  - destinations:       name_clean + entity_type + parent_id
  - festivals:          name_clean + destination_id
  - activities:         name_clean + activity_type + round(lat,1) + round(lon,1)

Per table outputs:
  1. ROC curve                     → <table>_roc.html
  2. Precision-Recall curve        → <table>_precision_recall.html
  3. Threshold selection chart     → <table>_threshold_selection.html
  4. Truth table (TP/FP/FN/TN)     → <table>_truth_table.csv  + terminal print
  5. False positive/negative pairs → <table>_fp_fn.csv

Outputs: data/splink_outputs/evaluation/
"""
from pathlib import Path
import json
import pandas as pd
from splink import Linker, DuckDBAPI

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized/splink_input"
MODEL_DIR  = ROOT / "data/splink_outputs/training"
OUTPUT_DIR = ROOT / "data/splink_outputs/evaluation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NUMERIC_COLS = {"lat", "lon", "star_rating", "rooms"}
THRESHOLD    = 0.8

# Sample large tables to keep evaluation tractable
SAMPLE_SIZE = {
    "destinations":   None,    # 17k — full
    "venues":         20_000,  # 222k — sample
    "accommodations": 20_000,  # 192k — sample
    "transport_hubs": None,    # 79k  — full
    "festivals":      None,    # 5k   — full
    "activities":     None,    # 27k  — full
}


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


def add_pseudo_labels(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Add integer true_label column using deterministic grouping rules."""
    if name == "destinations":
        key = (
            df["name_clean"].fillna("") + "|" +
            df["entity_type"].fillna("") + "|" +
            df["parent_id"].fillna("")
        )
    elif name == "festivals":
        key = (
            df["name_clean"].fillna("") + "|" +
            df["destination_id"].fillna("")
        )
    elif name == "activities":
        key = (
            df["name_clean"].fillna("") + "|" +
            df["activity_type"].fillna("") + "|" +
            df["lat"].round(1).astype(str) + "|" +
            df["lon"].round(1).astype(str)
        )
    else:
        # venues, accommodations, transport_hubs
        key = (
            df["name_clean"].fillna("") + "|" +
            df["lat"].round(2).astype(str) + "|" +
            df["lon"].round(2).astype(str)
        )
    label_map = {v: i for i, v in enumerate(key.unique())}
    df = df.copy()
    df["true_label"] = key.map(label_map)
    return df


def save_chart(chart, path: Path, title: str) -> None:
    chart.save(str(path))
    inject_title(path, title)


def run_table(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}")
    print(f"{'='*60}")

    df = load(name)
    sample_size = SAMPLE_SIZE.get(name)
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
        print(f"  (sampled {sample_size:,} rows from {len(load(name)):,})")
    df = add_pseudo_labels(df, name)

    n_labelled_groups = df["true_label"].nunique()
    n_true_pairs      = (df.groupby("true_label").size() > 1).sum()
    print(f"  pseudo-label groups : {n_labelled_groups:,}  ({n_true_pairs:,} with duplicates)")

    model = json.loads((MODEL_DIR / f"{name}_model.json").read_text())
    model["retain_intermediate_calculation_columns"] = True
    linker = Linker(df, model, db_api=DuckDBAPI())

    # ── 1. ROC curve ─────────────────────────────────────────────────
    print("  [1/5] ROC curve…")
    roc_path = OUTPUT_DIR / f"{name}_roc.html"
    save_chart(
        linker.evaluation.accuracy_analysis_from_labels_column(
            "true_label", output_type="roc"
        ),
        roc_path,
        f"{name} — ROC Curve",
    )
    print(f"  → {roc_path.relative_to(ROOT)}")

    # ── 2. Precision-Recall curve ────────────────────────────────────
    print("  [2/5] Precision-Recall curve…")
    pr_path = OUTPUT_DIR / f"{name}_precision_recall.html"
    save_chart(
        linker.evaluation.accuracy_analysis_from_labels_column(
            "true_label", output_type="precision_recall"
        ),
        pr_path,
        f"{name} — Precision-Recall",
    )
    print(f"  → {pr_path.relative_to(ROOT)}")

    # ── 3. Threshold selection chart ─────────────────────────────────
    print("  [3/5] Threshold selection chart…")
    ts_path = OUTPUT_DIR / f"{name}_threshold_selection.html"
    save_chart(
        linker.evaluation.accuracy_analysis_from_labels_column(
            "true_label",
            output_type="threshold_selection",
            add_metrics=["specificity", "f1"],
        ),
        ts_path,
        f"{name} — Threshold Selection",
    )
    print(f"  → {ts_path.relative_to(ROOT)}")

    # ── 4. Truth table (TP / FP / FN / TN) ──────────────────────────
    print("  [4/5] Truth table…")
    truth = linker.evaluation.accuracy_analysis_from_labels_column(
        "true_label",
        output_type="table",
        threshold_match_probability=THRESHOLD,
        add_metrics=["specificity", "npv", "accuracy", "f1"],
    )
    truth_df = truth.as_pandas_dataframe()
    truth_path = OUTPUT_DIR / f"{name}_truth_table.csv"
    truth_df.to_csv(truth_path, index=False)
    print(f"\n  Truth table @ threshold={THRESHOLD}:")
    print(truth_df.to_string(index=False))
    print(f"\n  → {truth_path.relative_to(ROOT)}")

    # ── 5. False positive / false negative pairs ─────────────────────
    print("\n  [5/5] False positive / false negative pairs…")
    fp_fn = linker.evaluation.prediction_errors_from_labels_column(
        "true_label",
        include_false_positives=True,
        include_false_negatives=True,
        threshold_match_probability=THRESHOLD,
    )
    fp_fn_df = fp_fn.as_pandas_dataframe()

    if not fp_fn_df.empty:
        fp_fn_path = OUTPUT_DIR / f"{name}_fp_fn.csv"
        fp_fn_df.to_csv(fp_fn_path, index=False)
        if "match_probability" in fp_fn_df.columns and "truth_label" in fp_fn_df.columns:
            fp = fp_fn_df[fp_fn_df["truth_label"] == "FP"]
            fn = fp_fn_df[fp_fn_df["truth_label"] == "FN"]
            print(f"  False positives : {len(fp):,}  (predicted match, actually different)")
            print(f"  False negatives : {len(fn):,}  (predicted non-match, actually same)")
        else:
            print(f"  FP/FN pairs     : {len(fp_fn_df):,} total")
            print(f"  cols: {fp_fn_df.columns.tolist()}")
        print(f"  → {fp_fn_path.relative_to(ROOT)}")
    else:
        print("  (no FP/FN pairs found at this threshold)")


if __name__ == "__main__":
    print("=== Splink Evaluation — 6 tables ===")
    for table in ["destinations", "venues", "accommodations", "transport_hubs", "festivals", "activities"]:
        run_table(table)
    print(f"\n=== Done — outputs in {OUTPUT_DIR.relative_to(ROOT)} ===")
