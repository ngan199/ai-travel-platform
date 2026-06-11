"""
Splink Linkage Model — Specify, estimate, and save per table.

For each of the 6 tables:
  1. Define comparison rules (Jaro-Winkler, distance, exact match)
  2. Build Linker with blocking rules from 02_blocking
  3. Estimate u probabilities via random sampling
  4. Estimate m probabilities via EM (one pass per blocking rule)
  5. Save match weights chart → HTML
  6. Save model parameters → JSON

Outputs:
  data/splink_outputs/training/<table>_match_weights.html
  data/splink_outputs/training/<table>_model.json
"""
from pathlib import Path
import pandas as pd
from splink import Linker, DuckDBAPI, block_on, SettingsCreator
import splink.comparison_library as cl

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized/splink_input"
OUTPUT_DIR = ROOT / "data/splink_outputs/training"
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


def train(name: str, df: pd.DataFrame, settings: SettingsCreator, em_rules: list) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}  ({len(df):,} rows)")
    print(f"{'='*60}")

    linker = Linker(df, settings, db_api=DuckDBAPI())

    print("  [1/3] Estimating u probabilities (random sampling)…")
    linker.training.estimate_u_using_random_sampling(max_pairs=1_000_000)

    print("  [2/3] Estimating m probabilities (EM)…")
    for rule in em_rules:
        linker.training.estimate_parameters_using_expectation_maximisation(rule)

    print("  [3/3] Saving outputs…")
    chart_path = OUTPUT_DIR / f"{name}_match_weights.html"
    linker.visualisations.match_weights_chart().save(str(chart_path))
    inject_title(chart_path, f"{name} — Match Weights")

    model_path = OUTPUT_DIR / f"{name}_model.json"
    linker.misc.save_model_to_json(str(model_path), overwrite=True)

    print(f"  match weights → {chart_path.relative_to(ROOT)}")
    print(f"  model JSON    → {model_path.relative_to(ROOT)}")


# ── Table definitions ────────────────────────────────────────────────────────

def run_destinations():
    df = load("destinations")
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("name_clean", [0.95, 0.88]),
            cl.ExactMatch("entity_type"),
            cl.ExactMatch("parent_id"),
            cl.DistanceInKMAtThresholds("lat", "lon", [1, 10, 50]),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_clean"),
            block_on("substr(name_clean, 1, 6)", "entity_type"),
            block_on("parent_id", "substr(name_clean, 1, 4)"),
        ],
    )
    em_rules = [
        block_on("substr(name_clean, 1, 6)", "entity_type"),
        block_on("parent_id", "substr(name_clean, 1, 4)"),
    ]
    train("destinations", df, settings, em_rules)


def run_venues():
    df = load("venues")
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("name_clean", [0.95, 0.88]),
            cl.ExactMatch("entity_type"),
            cl.ExactMatch("destination_id"),
            cl.DistanceInKMAtThresholds("lat", "lon", [0.1, 1, 10]),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_clean"),
            block_on("destination_id", "substr(name_clean, 1, 6)"),
            block_on("round(lat, 2)", "round(lon, 2)"),
        ],
    )
    em_rules = [
        block_on("destination_id", "substr(name_clean, 1, 6)"),
        block_on("round(lat, 2)", "round(lon, 2)"),
    ]
    train("venues", df, settings, em_rules)


def run_accommodations():
    df = load("accommodations")
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("name_clean", [0.95, 0.88]),
            cl.ExactMatch("entity_type"),
            cl.ExactMatch("destination_id"),
            cl.DistanceInKMAtThresholds("lat", "lon", [0.1, 1, 10]),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_clean"),
            block_on("round(lat, 2)", "round(lon, 2)"),
            block_on("destination_id", "substr(name_clean, 1, 8)"),
        ],
    )
    em_rules = [
        block_on("round(lat, 2)", "round(lon, 2)"),
        block_on("destination_id", "substr(name_clean, 1, 8)"),
    ]
    train("accommodations", df, settings, em_rules)


def run_transport_hubs():
    df = load("transport_hubs")
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("name_clean", [0.95, 0.88]),
            cl.ExactMatch("entity_type"),
            cl.ExactMatch("iata_code"),
            cl.DistanceInKMAtThresholds("lat", "lon", [0.1, 1, 10]),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_clean"),
            block_on("iata_code"),
            block_on("round(lat, 2)", "round(lon, 2)", "entity_type"),
        ],
    )
    em_rules = [
        block_on("iata_code"),
        block_on("round(lat, 2)", "round(lon, 2)", "entity_type"),
    ]
    train("transport_hubs", df, settings, em_rules)


def run_festivals():
    df = load("festivals")
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("name_clean", [0.95, 0.88]),
            cl.ExactMatch("festival_type"),
            cl.ExactMatch("destination_id"),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_clean"),
            block_on("destination_id", "substr(name_clean, 1, 5)"),
        ],
    )
    em_rules = [
        block_on("destination_id", "substr(name_clean, 1, 5)"),
    ]
    train("festivals", df, settings, em_rules)


def run_activities():
    df = load("activities")
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("name_clean", [0.95, 0.88]),
            cl.ExactMatch("activity_type"),
            cl.ExactMatch("destination_id"),
            cl.DistanceInKMAtThresholds("lat", "lon", [0.1, 1, 10]),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_clean"),
            block_on("activity_type", "round(lat, 1)", "round(lon, 1)"),
            block_on("destination_id", "substr(name_clean, 1, 6)"),
        ],
    )
    em_rules = [
        block_on("activity_type", "round(lat, 1)", "round(lon, 1)"),
        block_on("destination_id", "substr(name_clean, 1, 6)"),
    ]
    train("activities", df, settings, em_rules)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Splink Linkage Model Training — 6 tables ===")
    run_destinations()
    run_venues()
    run_accommodations()
    run_transport_hubs()
    run_festivals()
    run_activities()
    print(f"\n=== Done — outputs in {OUTPUT_DIR.relative_to(ROOT)} ===")
