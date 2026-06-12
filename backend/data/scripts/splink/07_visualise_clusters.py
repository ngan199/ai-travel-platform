"""
Visualise final cluster results — 6 tables.

Per table (3 charts):
  1. Cluster size distribution   — bar chart (how many clusters of each size)
  2. Top 20 largest clusters     — horizontal bar chart (name + member count)
  3. Geographic scatter          — world map of multi-record clusters, coloured by size

Output: data/splink_outputs/clusters/<table>_size_dist.html
                                  <table>_top_clusters.html
                                  <table>_geo.html
"""
from pathlib import Path
import pandas as pd
import altair as alt

ROOT       = Path(__file__).parents[3]
NORM       = ROOT / "data/normalized/splink_input"
OUTPUT_DIR = ROOT / "data/splink_outputs/clusters"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DARK_BLUE = "#1e3a5f"


def inject_title(path: Path, title: str) -> None:
    html = path.read_text(encoding="utf-8")
    html = html.replace("<head>", f"<head>\n  <title>{title}</title>", 1)
    html = html.replace(
        "<body>",
        "<body>\n"
        f'  <div style="font-family:sans-serif;padding:12px 20px;'
        f'background:{DARK_BLUE};color:#fff;font-size:18px;font-weight:bold;">'
        f"{title}</div>",
        1,
    )
    path.write_text(html, encoding="utf-8")


def save(chart: alt.Chart, path: Path, title: str) -> None:
    chart.save(str(path))
    inject_title(path, title)
    print(f"  → {path.relative_to(ROOT)}")


def load(name: str) -> pd.DataFrame:
    path = NORM / f"{name}_clustered.csv"
    return pd.read_csv(path, dtype=str, low_memory=False)


def chart_size_distribution(df: pd.DataFrame, name: str) -> alt.Chart:
    sizes = df.groupby("cluster_id").size().reset_index(name="cluster_size")
    dist = sizes["cluster_size"].value_counts().reset_index()
    dist.columns = ["cluster_size", "count"]
    dist = dist[dist["cluster_size"] <= 20].sort_values("cluster_size")

    return (
        alt.Chart(dist)
        .mark_bar(color="#2a7abf")
        .encode(
            x=alt.X("cluster_size:O", title="Cluster size (number of records)", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("count:Q", title="Number of clusters"),
            tooltip=["cluster_size", "count"],
        )
        .properties(
            width=700, height=350,
            title=alt.TitleParams(f"{name} — Cluster Size Distribution", fontSize=14),
        )
        .configure_axis(grid=False)
        .configure_view(stroke=None)
        .interactive()
    )


def chart_top_clusters(df: pd.DataFrame, name: str, label_col: str) -> alt.Chart:
    sizes = df.groupby("cluster_id").size().reset_index(name="n_records")
    merged = df.drop_duplicates("cluster_id")[["cluster_id", label_col]].merge(sizes, on="cluster_id")
    top = merged.nlargest(20, "n_records").copy()
    top["label"] = top[label_col].fillna("(unknown)").str[:50]

    return (
        alt.Chart(top)
        .mark_bar(color="#2a7abf")
        .encode(
            x=alt.X("n_records:Q", title="Number of records in cluster"),
            y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelLimit=350)),
            tooltip=["label", "n_records", "cluster_id"],
        )
        .properties(
            width=700, height=450,
            title=alt.TitleParams(f"{name} — Top 20 Largest Clusters", fontSize=14),
        )
        .configure_axis(grid=False)
        .configure_view(stroke=None)
        .interactive()
    )


def chart_geo(df: pd.DataFrame, name: str) -> alt.Chart | None:
    if "lat" not in df.columns or "lon" not in df.columns:
        return None
    df = df.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    sizes = df.groupby("cluster_id").size().reset_index(name="cluster_size")
    multi = sizes[sizes["cluster_size"] > 1]
    if multi.empty:
        return None

    # One point per cluster — use first record's coordinates as centroid proxy
    first = df.drop_duplicates("cluster_id")[["cluster_id", "lat", "lon", "name"]].dropna(subset=["lat", "lon"])
    plot_df = first.merge(multi, on="cluster_id")
    plot_df = plot_df[
        plot_df["lat"].between(-90, 90) &
        plot_df["lon"].between(-180, 180)
    ]
    if plot_df.empty:
        return None

    plot_df["size_capped"] = plot_df["cluster_size"].clip(upper=20)
    plot_df["label"] = plot_df["name"].fillna("").str[:50]

    background = (
        alt.Chart(alt.sphere())
        .mark_geoshape(fill="#d0e8f5", stroke="white")
        .project("naturalEarth1")
    )
    graticule = (
        alt.Chart(alt.graticule())
        .mark_geoshape(stroke="#ccc", strokeWidth=0.3)
        .project("naturalEarth1")
    )
    points = (
        alt.Chart(plot_df)
        .mark_circle(opacity=0.6)
        .encode(
            longitude="lon:Q",
            latitude="lat:Q",
            size=alt.Size("size_capped:Q", scale=alt.Scale(range=[20, 300]), legend=alt.Legend(title="Cluster size")),
            color=alt.Color("size_capped:Q", scale=alt.Scale(scheme="orangered"), legend=None),
            tooltip=["label:N", "cluster_size:Q", "cluster_id:N"],
        )
        .project("naturalEarth1")
    )

    return (
        (background + graticule + points)
        .properties(
            width=800, height=450,
            title=alt.TitleParams(f"{name} — Multi-record Clusters (Geographic)", fontSize=14),
        )
        .configure_view(stroke=None)
        .interactive()
    )


TABLE_LABEL_COL = {
    "destinations":   "name",
    "venues":         "name",
    "accommodations": "name",
    "transport_hubs": "name",
    "festivals":      "name",
    "activities":     "name",
}


def run_table(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name.upper()}")
    print(f"{'='*60}")

    df = load(name)
    label_col = TABLE_LABEL_COL[name]

    n_total    = len(df)
    sizes      = df.groupby("cluster_id").size()
    n_clusters = len(sizes)
    n_multi    = (sizes > 1).sum()
    print(f"  {n_total:,} records → {n_clusters:,} clusters  ({n_multi:,} multi-record)")

    # 1. Size distribution
    save(
        chart_size_distribution(df, name),
        OUTPUT_DIR / f"{name}_size_dist.html",
        f"{name} — Cluster Size Distribution",
    )

    # 2. Top 20 clusters
    save(
        chart_top_clusters(df, name, label_col),
        OUTPUT_DIR / f"{name}_top_clusters.html",
        f"{name} — Top 20 Largest Clusters",
    )

    # 3. Geographic scatter
    geo = chart_geo(df, name)
    if geo:
        save(
            geo,
            OUTPUT_DIR / f"{name}_geo.html",
            f"{name} — Multi-record Clusters (Geographic)",
        )
    else:
        print("  (geo skipped — no coordinates)")


if __name__ == "__main__":
    print("=== Cluster Visualisation — 6 tables ===")
    for table in ["destinations", "venues", "accommodations", "transport_hubs", "festivals", "activities"]:
        run_table(table)
    print(f"\n=== Done — charts in {OUTPUT_DIR.relative_to(ROOT)} ===")
