#!/usr/bin/env python3
"""
Part 6 — Step 06: Interactive graph visualization.

Produces four standalone HTML files (no server required):

  1. erkg_viz.html     — Taxonomy backbone + top entities spread across classes
  2. lex_viz.html      — Lexical co-occurrence graph, top-300 lemmas by frequency
  3. taxonomy_viz.html — Pure skos:broader/related hierarchy (clean tree)
  4. ent_rank_viz.html — Top 500 entities by NER count, sized & colored by type

Inputs:
  - data/output/erkg.json
  - data/output/lex.json
  - data/output/ent.json

Outputs:
  - data/output/viz/erkg_viz.html
  - data/output/viz/lex_viz.html
  - data/output/viz/taxonomy_viz.html
  - data/output/viz/ent_rank_viz.html
"""
import json
import pathlib
import re
import time
from collections import defaultdict

from pyvis.network import Network

ROOT       = pathlib.Path(__file__).parents[3]
ERKG_IN    = ROOT / "data" / "output" / "erkg.json"
LEX_IN     = ROOT / "data" / "output" / "lex.json"
ENT_IN     = ROOT / "data" / "output" / "ent.json"
OUT_DIR    = ROOT / "data" / "output" / "viz"
ERKG_OUT   = OUT_DIR / "erkg_viz.html"
LEX_OUT    = OUT_DIR / "lex_viz.html"
TAX_OUT    = OUT_DIR / "taxonomy_viz.html"
RANK_OUT   = OUT_DIR / "ent_rank_viz.html"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Colour palette ────────────────────────────────────────────────────────────

TAXONOMY_COLOR  = "#F4A235"   # amber — ontology concepts
DATAREC_COLOR   = "#B0BEC5"   # grey  — raw data records (not shown in erkg viz)

# travel: class → colour for entity nodes
CLASS_COLORS: dict[str, str] = {
    "travel:Country":       "#42A5F5",   # blue
    "travel:City":          "#66BB6A",   # green
    "travel:Region":        "#AB47BC",   # purple
    "travel:Destination":   "#26C6DA",   # cyan
    "travel:Hotel":         "#EF5350",   # red
    "travel:Hostel":        "#EC407A",   # pink
    "travel:Resort":        "#FF7043",   # deep orange
    "travel:Accommodation": "#FF8A65",   # light orange
    "travel:Airport":       "#29B6F6",   # light blue
    "travel:TrainStation":  "#5C6BC0",   # indigo
    "travel:Hub":           "#7E57C2",   # deep purple
    "travel:Festival":      "#FFCA28",   # yellow
    "travel:Event":         "#FFA726",   # orange
    "travel:Activity":      "#26A69A",   # teal
    "travel:Venue":         "#8D6E63",   # brown
    "travel:Attraction":    "#78909C",   # blue-grey
}
DEFAULT_ENTITY_COLOR = "#90A4AE"

# edge colours
EDGE_COLORS: dict[str, str] = {
    "skos:broader":              "#F4A235",
    "skos:related":              "#FDD835",
    "rdf:type":                  "#90CAF9",
    "travel:follows_lexically":  "#4DB6AC",
    "travel:co_occurs_with":     "#CE93D8",
}


def short_label(node_id: str) -> str:
    """Return a readable short label from a URN/IRI or lemma key."""
    # travel:Country → "Country"
    if node_id.startswith("travel:"):
        return node_id[7:]
    # sz:12345 → "12345"
    if node_id.startswith("sz:"):
        return node_id[3:]
    # NOUN.paris → "paris"
    if node_id.startswith("NOUN."):
        return node_id[5:]
    return node_id


def lemma_to_display(lemma_key: str) -> str:
    """NOUN.new NOUN.york → 'new york'"""
    parts = []
    for tok in lemma_key.split():
        if tok.startswith("NOUN."):
            parts.append(tok[5:])
        else:
            parts.append(tok)
    return " ".join(parts)


# ── ERKG Visualization ────────────────────────────────────────────────────────

TOP_ENTITIES = 200   # total entity nodes to include (spread across classes)
TOP_PER_CLASS = 15   # max entities per taxonomy class

def build_erkg_viz() -> None:
    t0 = time.time()
    print("[ERKG] Loading erkg.json …")
    with ERKG_IN.open(encoding="utf-8") as f:
        data = json.load(f)

    all_nodes: list[dict] = data["nodes"]
    all_edges: list[dict] = data["edges"]

    # ── Split by kind ─────────────────────────────────────────────────────────
    taxonomy_nodes = [n for n in all_nodes if n.get("kind") == "TAXONOMY"]
    entity_nodes   = [n for n in all_nodes if n.get("kind") == "ENTITY"]

    print(f"[ERKG] {len(taxonomy_nodes)} taxonomy nodes, "
          f"{len(entity_nodes):,} entity nodes")

    node_by_id = {n["id"]: n for n in all_nodes}

    # ── Derive rtype from rdf:type edges (not stored on node itself) ──────────
    entity_rtype: dict[str, str] = {}   # entity_id → taxonomy_id
    for e in all_edges:
        if e["key"] == "rdf:type":
            entity_rtype[e["source"]] = e["target"]

    # Attach rtype onto each entity node for easy access
    for n in entity_nodes:
        n["_rtype"] = entity_rtype.get(n["id"], "")

    # ── Select entities: top-N per taxonomy class (spread) ───────────────────
    by_class: dict[str, list[dict]] = defaultdict(list)
    for n in entity_nodes:
        rt = n["_rtype"]
        if rt:
            by_class[rt].append(n)

    # Sort each class bucket by count desc, take top-per-class
    selected: list[dict] = []
    for rt, bucket in by_class.items():
        bucket.sort(key=lambda n: n.get("count", 0), reverse=True)
        selected.extend(bucket[:TOP_PER_CLASS])

    # If under budget, top-up with highest-count remaining
    selected_ids = {n["id"] for n in selected}
    if len(selected) < TOP_ENTITIES:
        remaining = sorted(
            [n for n in entity_nodes if n["id"] not in selected_ids],
            key=lambda n: n.get("count", 0), reverse=True
        )
        selected.extend(remaining[:TOP_ENTITIES - len(selected)])

    top_entities   = selected
    top_entity_ids = {n["id"] for n in top_entities}

    # taxonomy node IDs
    taxonomy_ids = {n["id"] for n in taxonomy_nodes}
    keep_ids = taxonomy_ids | top_entity_ids

    # Filter edges: only those where both endpoints are in keep_ids
    kept_edges = []
    for e in all_edges:
        s, t = e["source"], e["target"]
        if s in keep_ids and t in keep_ids:
            kept_edges.append(e)

    print(f"[ERKG] Showing {len(taxonomy_nodes)} taxonomy + "
          f"{len(top_entities)} entities, {len(kept_edges)} edges")

    # ── Build Pyvis network ───────────────────────────────────────────────────
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#1A1A2E",
        font_color="#EEEEEE",
        directed=True,
        notebook=False,
    )
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.3,
        spring_length=120,
        spring_strength=0.04,
        damping=0.09,
    )

    # Add taxonomy nodes
    for n in taxonomy_nodes:
        nid   = n["id"]
        label = short_label(nid)
        title = (
            f"<b>{n.get('text', label)}</b><br>"
            f"Kind: TAXONOMY<br>"
            f"Lemma: {n.get('lemma','')}<br>"
            f"Def: {n.get('defn','')}<br>"
            f"Count: {n.get('count',0)}"
        )
        net.add_node(
            nid,
            label=label,
            title=title,
            color=TAXONOMY_COLOR,
            size=22,
            shape="diamond",
            font={"size": 14, "bold": True},
            borderWidth=2,
            borderWidthSelected=4,
        )

    # Add top-entity nodes
    max_count = max((n.get("count", 1) for n in top_entities), default=1)
    for n in top_entities:
        nid      = n["id"]
        rtype    = n.get("_rtype", "")
        color    = CLASS_COLORS.get(rtype, DEFAULT_ENTITY_COLOR)
        count    = n.get("count", 0)
        size     = max(8, min(24, int(8 + 16 * (count / max_count) ** 0.4)))
        label    = n.get("text", short_label(nid))[:30]
        title    = (
            f"<b>{n.get('text', nid)}</b><br>"
            f"Type: {short_label(rtype)}<br>"
            f"Count: {count}<br>"
            f"IRI: {nid}"
        )
        net.add_node(
            nid,
            label=label,
            title=title,
            color=color,
            size=size,
            shape="dot",
            font={"size": 10},
        )

    # Add edges
    for e in kept_edges:
        key   = e.get("key", "")
        color = EDGE_COLORS.get(key, "#888888")
        width = 3 if key in ("skos:broader", "skos:related") else 1
        net.add_edge(
            e["source"],
            e["target"],
            title=key,
            color={"color": color, "opacity": 0.7},
            width=width,
            arrows="to",
        )

    # Legend via title injection
    legend_html = _legend_html(
        title="Travel Knowledge Graph — Taxonomy + Top Entities",
        items=[
            (TAXONOMY_COLOR, "Taxonomy concept (diamond)"),
            (CLASS_COLORS["travel:Country"], "Country"),
            (CLASS_COLORS["travel:City"], "City"),
            (CLASS_COLORS["travel:Hotel"], "Hotel / Accommodation"),
            (CLASS_COLORS["travel:Airport"], "Airport / Transport Hub"),
            (CLASS_COLORS["travel:Festival"], "Festival / Event"),
            (CLASS_COLORS["travel:Activity"], "Activity"),
            (DEFAULT_ENTITY_COLOR, "Other entity type"),
        ],
        edge_items=[
            (EDGE_COLORS["skos:broader"], "skos:broader (taxonomy hierarchy)"),
            (EDGE_COLORS["rdf:type"], "rdf:type (entity → concept)"),
        ],
        note=f"Showing full taxonomy ({len(taxonomy_nodes)} nodes) + "
             f"{len(top_entities)} entities (top {TOP_PER_CLASS} per class by frequency)",
    )

    _write_html(net, ERKG_OUT, legend_html)
    print(f"[ERKG] → {ERKG_OUT.relative_to(ROOT)}  ({time.time()-t0:.0f}s)")


# ── Lexical graph visualization ───────────────────────────────────────────────

TOP_LEX_NODES = 300

def build_lex_viz() -> None:
    t0 = time.time()
    print("[LEX]  Loading lex.json …")
    with LEX_IN.open(encoding="utf-8") as f:
        data = json.load(f)

    all_nodes: list[dict] = data["nodes"]
    all_edges: list[dict] = data["edges"]

    print(f"[LEX]  {len(all_nodes):,} nodes, {len(all_edges):,} edges")

    # Pick top-N nodes by count
    sorted_nodes = sorted(all_nodes, key=lambda n: n.get("count", 0), reverse=True)
    top_nodes    = sorted_nodes[:TOP_LEX_NODES]
    top_ids      = {n["id"] for n in top_nodes}

    max_count = max((n.get("count", 1) for n in top_nodes), default=1)

    # Filter edges: both endpoints in top set
    co_edges  = []
    seq_edges = []
    # Deduplicate co_occurs edges (bidirectional → one undirected)
    seen_co: set[tuple] = set()
    for e in all_edges:
        s, t = e["source"], e["target"]
        if s not in top_ids or t not in top_ids:
            continue
        key = e.get("key", "")
        if key == "travel:co_occurs_with":
            pair = tuple(sorted([s, t]))
            if pair not in seen_co:
                seen_co.add(pair)
                co_edges.append(e)
        elif key == "travel:follows_lexically":
            seq_edges.append(e)

    print(f"[LEX]  Showing {len(top_nodes)} nodes | "
          f"{len(seq_edges)} follows_lexically | "
          f"{len(co_edges)} co_occurs_with")

    # ── Build Pyvis network ───────────────────────────────────────────────────
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#0D1B2A",
        font_color="#EEEEEE",
        directed=False,
        notebook=False,
    )
    net.barnes_hut(
        gravity=-2500,
        central_gravity=0.2,
        spring_length=100,
        spring_strength=0.03,
        damping=0.09,
    )

    for n in top_nodes:
        nid   = n["id"]
        count = n.get("count", 1)
        size  = max(8, min(40, int(8 + 32 * (count / max_count) ** 0.5)))
        label = lemma_to_display(nid)
        insts = n.get("inst", [])
        title = (
            f"<b>{label}</b><br>"
            f"Lemma key: {nid}<br>"
            f"Count: {count}<br>"
            f"Chunks: {len(insts)}"
        )
        net.add_node(
            nid,
            label=label,
            title=title,
            color={"background": "#4DB6AC", "border": "#00897B",
                   "highlight": {"background": "#80CBC4", "border": "#00695C"}},
            size=size,
            font={"size": max(9, min(16, size - 2))},
        )

    # co_occurs edges (undirected, purple, weight-scaled)
    max_co_w = max((e.get("weight", 1) for e in co_edges), default=1)
    for e in co_edges:
        w = e.get("weight", 1)
        width = max(1, min(6, int(1 + 5 * (w / max_co_w) ** 0.5)))
        net.add_edge(
            e["source"], e["target"],
            title=f"co_occurs_with (w={w})",
            color={"color": "#CE93D8", "opacity": 0.5},
            width=width,
        )

    # follows_lexically edges (directed, teal, thin)
    net.directed = True
    for e in seq_edges:
        net.add_edge(
            e["source"], e["target"],
            title="follows_lexically",
            color={"color": "#4DB6AC", "opacity": 0.8},
            width=1,
            arrows="to",
            dashes=True,
        )

    legend_html = _legend_html(
        title="Lexical Co-occurrence Graph",
        items=[
            ("#4DB6AC", "Lemma node (size ∝ frequency)"),
        ],
        edge_items=[
            (EDGE_COLORS["travel:co_occurs_with"],    "co_occurs_with (solid, width ∝ strength)"),
            (EDGE_COLORS["travel:follows_lexically"], "follows_lexically (dashed, directed)"),
        ],
        note=f"Top {len(top_nodes)} lemmas by chunk frequency · "
             f"{len(co_edges)} co-occurrence + {len(seq_edges)} sequential edges",
    )

    _write_html(net, LEX_OUT, legend_html)
    print(f"[LEX]  → {LEX_OUT.relative_to(ROOT)}  ({time.time()-t0:.0f}s)")


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _legend_html(
    title: str,
    items: list[tuple[str, str]],
    edge_items: list[tuple[str, str]],
    note: str = "",
) -> str:
    node_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
        f'<div style="width:14px;height:14px;border-radius:50%;'
        f'background:{c};flex-shrink:0"></div>'
        f'<span style="font-size:12px">{label}</span></div>'
        for c, label in items
    )
    edge_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
        f'<div style="width:24px;height:3px;background:{c};flex-shrink:0"></div>'
        f'<span style="font-size:12px">{label}</span></div>'
        for c, label in edge_items
    )
    note_html = f'<p style="font-size:11px;color:#aaa;margin-top:8px">{note}</p>' if note else ""
    return f"""
<div id="legend" style="
    position:fixed;top:16px;right:16px;z-index:1000;
    background:rgba(10,10,30,0.88);color:#eee;
    border:1px solid #444;border-radius:8px;
    padding:14px 18px;min-width:240px;max-width:320px;
    font-family:sans-serif;backdrop-filter:blur(4px)">
  <b style="font-size:14px">{title}</b>
  <hr style="border-color:#444;margin:8px 0">
  <div style="font-size:11px;color:#aaa;margin-bottom:6px">NODES</div>
  {node_rows}
  <div style="font-size:11px;color:#aaa;margin:8px 0 4px">EDGES</div>
  {edge_rows}
  {note_html}
</div>
"""


def _write_html(net: Network, out_path: pathlib.Path, legend_html: str) -> None:
    """Generate pyvis HTML and inject the legend panel."""
    tmp = out_path.with_suffix(".tmp.html")
    net.save_graph(str(tmp))

    html = tmp.read_text(encoding="utf-8")

    # Inject legend just before </body>
    html = html.replace("</body>", legend_html + "\n</body>")

    out_path.write_text(html, encoding="utf-8")
    tmp.unlink(missing_ok=True)


# ── Taxonomy hierarchy visualization ─────────────────────────────────────────

def build_taxonomy_viz() -> None:
    t0 = time.time()
    print("[TAX]  Loading taxonomy from erkg.json …")
    with ERKG_IN.open(encoding="utf-8") as f:
        data = json.load(f)

    taxonomy_nodes = [n for n in data["nodes"] if n.get("kind") == "TAXONOMY"]
    taxonomy_ids   = {n["id"] for n in taxonomy_nodes}
    tax_edges      = [
        e for e in data["edges"]
        if e["source"] in taxonomy_ids and e["target"] in taxonomy_ids
    ]
    print(f"[TAX]  {len(taxonomy_nodes)} nodes, {len(tax_edges)} edges")

    net = Network(
        height="900px",
        width="100%",
        bgcolor="#0F0F1A",
        font_color="#EEEEEE",
        directed=True,
        notebook=False,
    )
    net.set_options("""
    {
      "layout": { "hierarchical": {
        "enabled": true,
        "direction": "UD",
        "sortMethod": "directed",
        "nodeSpacing": 160,
        "levelSeparation": 120
      }},
      "physics": { "enabled": false }
    }
    """)

    for n in taxonomy_nodes:
        nid   = n["id"]
        label = n.get("text", short_label(nid))
        defn  = n.get("defn", "")
        lemma = n.get("lemma", "")
        title = f"<b>{label}</b><br>{defn}<br><i>{nid}</i><br>Lemma: {lemma}"
        net.add_node(
            nid,
            label=label,
            title=title,
            color={
                "background": TAXONOMY_COLOR,
                "border": "#C17B1A",
                "highlight": {"background": "#FFD580", "border": "#A0631A"},
            },
            size=20,
            shape="diamond",
            font={"size": 13, "bold": True, "color": "#111"},
        )

    for e in tax_edges:
        key   = e.get("key", "")
        color = EDGE_COLORS.get(key, "#888")
        dashes = key == "skos:related"
        net.add_edge(
            e["source"], e["target"],
            title=key,
            color={"color": color, "opacity": 0.85},
            width=2 if key == "skos:broader" else 1,
            arrows="to",
            dashes=dashes,
        )

    legend_html = _legend_html(
        title="Travel Ontology Taxonomy",
        items=[(TAXONOMY_COLOR, "Concept node")],
        edge_items=[
            (EDGE_COLORS["skos:broader"], "skos:broader (solid — parent hierarchy)"),
            (EDGE_COLORS["skos:related"], "skos:related (dashed — lateral link)"),
        ],
        note=f"{len(taxonomy_nodes)} concepts · {len(tax_edges)} relations · hierarchical layout",
    )
    _write_html(net, TAX_OUT, legend_html)
    print(f"[TAX]  → {TAX_OUT.relative_to(ROOT)}  ({time.time()-t0:.0f}s)")


# ── Entity rank visualization (ent.json) ──────────────────────────────────────

TOP_ENT_RANK = 500

def build_ent_rank_viz() -> None:
    t0 = time.time()
    print("[ENT]  Loading ent.json …")

    entries: list[dict] = []
    with ENT_IN.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # Only ER entities (source = Entity_Resolution) with count > 0
    er_entries = [
        e for e in entries
        if e.get("span", {}).get("source") == "Entity_Resolution"
        and e.get("count", 0) > 0
    ]
    er_entries.sort(key=lambda e: e.get("count", 0), reverse=True)
    top = er_entries[:TOP_ENT_RANK]
    print(f"[ENT]  {len(er_entries):,} ER entities with count>0 → showing top {len(top)}")

    max_count = max((e.get("count", 1) for e in top), default=1)

    # Build co-occurrence edges from shared chunks (inst overlap)
    # chunk_id → list of entity lemma_keys
    chunk_to_ents: dict[int, list[str]] = defaultdict(list)
    top_keys = {e["lemma_key"] for e in top}
    for e in top:
        for inst in e.get("inst", []):
            cid = inst.get("chunk_id", -1)
            if cid >= 0:
                chunk_to_ents[cid].append(e["lemma_key"])

    # Count pair co-occurrences
    pair_counts: dict[tuple, int] = defaultdict(int)
    for cid, keys in chunk_to_ents.items():
        keys_in_top = [k for k in keys if k in top_keys]
        for i in range(len(keys_in_top)):
            for j in range(i + 1, len(keys_in_top)):
                a, b = keys_in_top[i], keys_in_top[j]
                if a != b:
                    pair = tuple(sorted([a, b]))
                    pair_counts[pair] += 1

    # Keep only pairs with co-occurrence ≥ 2 (noise reduction)
    strong_pairs = {p: c for p, c in pair_counts.items() if c >= 2}
    print(f"[ENT]  {len(strong_pairs):,} strong co-occurrence pairs (≥2)")

    # ── Build erkg entity_id → travel_type lookup ─────────────────────────────
    with ERKG_IN.open(encoding="utf-8") as f:
        erkg = json.load(f)
    entity_rtype: dict[str, str] = {}
    for e in erkg["edges"]:
        if e["key"] == "rdf:type":
            entity_rtype[e["source"]] = e["target"]

    # lemma_key → travel_type (via ent.json span.iri → erkg entity_id)
    lk_to_type: dict[str, str] = {}
    for e in top:
        iri = e.get("span", {}).get("iri")
        if iri:
            lk_to_type[e["lemma_key"]] = entity_rtype.get(iri, "")

    net = Network(
        height="950px",
        width="100%",
        bgcolor="#0A0A1A",
        font_color="#EEEEEE",
        directed=False,
        notebook=False,
    )
    net.barnes_hut(
        gravity=-2000,
        central_gravity=0.15,
        spring_length=130,
        spring_strength=0.02,
        damping=0.09,
    )

    for e in top:
        lk    = e["lemma_key"]
        count = e.get("count", 0)
        rtype = lk_to_type.get(lk, "")
        color = CLASS_COLORS.get(rtype, DEFAULT_ENTITY_COLOR)
        size  = max(8, min(40, int(8 + 32 * (count / max_count) ** 0.4)))
        label = e.get("span", {}).get("text", lemma_to_display(lk))[:28]
        title = (
            f"<b>{label}</b><br>"
            f"Type: {short_label(rtype) or 'unknown'}<br>"
            f"NER count: {count}<br>"
            f"Lemma: {lk}<br>"
            f"IRI: {e.get('span',{}).get('iri','')}"
        )
        net.add_node(
            lk,
            label=label,
            title=title,
            color={"background": color, "border": "#222",
                   "highlight": {"background": color, "border": "#fff"}},
            size=size,
            font={"size": max(9, min(14, size - 3))},
        )

    max_pair = max(strong_pairs.values(), default=1)
    for (a, b), cnt in strong_pairs.items():
        width = max(1, min(6, int(1 + 5 * (cnt / max_pair) ** 0.5)))
        net.add_edge(
            a, b,
            title=f"co-occurs in {cnt} chunk(s)",
            color={"color": "#546E7A", "opacity": 0.4},
            width=width,
        )

    legend_html = _legend_html(
        title="Entity Frequency & Co-occurrence",
        items=[
            (CLASS_COLORS["travel:Country"],  "Country"),
            (CLASS_COLORS["travel:City"],     "City"),
            (CLASS_COLORS["travel:Hotel"],    "Hotel / Accommodation"),
            (CLASS_COLORS["travel:Airport"],  "Airport / Transport"),
            (CLASS_COLORS["travel:Festival"], "Festival / Event"),
            (CLASS_COLORS["travel:Activity"], "Activity"),
            (CLASS_COLORS["travel:Venue"],    "Venue"),
            (DEFAULT_ENTITY_COLOR,            "Other / unknown"),
        ],
        edge_items=[
            ("#546E7A", "co-occurs in ≥2 chunks (width ∝ strength)"),
        ],
        note=f"Top {len(top)} entities by NER frequency · node size ∝ count",
    )
    _write_html(net, RANK_OUT, legend_html)
    print(f"[ENT]  → {RANK_OUT.relative_to(ROOT)}  ({time.time()-t0:.0f}s)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    print("=== Step 06 — Visualize Graphs ===\n")

    build_erkg_viz()
    print()
    build_lex_viz()
    print()
    build_taxonomy_viz()
    print()
    build_ent_rank_viz()

    print(f"\n=== Done in {time.time()-t0:.0f}s ===")
    print(f"\nOutputs:")
    for p in [ERKG_OUT, LEX_OUT, TAX_OUT, RANK_OUT]:
        print(f"  {p}")


if __name__ == "__main__":
    main()
