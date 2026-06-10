"""
Test domain.ttl with rdflib and generate an interactive schema visualization.
Outputs:
  - validation report to stdout
  - ontology/schema_visualization.html (interactive pyvis graph)
"""
import sys
from pathlib import Path
from collections import defaultdict

from rdflib import Graph, Namespace, RDF, SKOS, URIRef
from rdflib.namespace import DC, RDFS
import networkx as nx
from pyvis.network import Network

ONTOLOGY_DIR = Path(__file__).parent
TTL_PATH = ONTOLOGY_DIR / "domain.ttl"

TRAVEL = Namespace("https://travel-ontology.ai/vocab#")

BRANCH_COLORS = {
    "Tourism":             "#1ABC9C",
    "Place":               "#4A90D9",
    "TravelExperience":    "#E67E22",
    "Lodging":             "#27AE60",
    "Transport":           "#8E44AD",
    "TravelClassification":"#C0392B",
    "LocalKnowledge":      "#16A085",
    "PracticalInfo":       "#2C3E50",
    "TemporalConcept":     "#F39C12",
    "TravelerContent":     "#7F8C8D",
}


def local_name(uri: URIRef) -> str:
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.split("/")[-1]


def get_branch(g: Graph, concept: URIRef) -> str:
    name = local_name(concept)
    if name == "Tourism":
        return "Tourism"
    for broader in g.objects(concept, SKOS.broader):
        if local_name(broader) == "Tourism":
            return name
        branch = get_branch(g, broader)
        if branch:
            return branch
    return "Tourism"


def run_tests(g: Graph) -> bool:
    print("=" * 60)
    print("DOMAIN.TTL VALIDATION REPORT")
    print("=" * 60)

    ok = True
    concepts = list(g.subjects(RDF.type, SKOS.Concept))

    print(f"\nTotal triples      : {len(g)}")
    print(f"Concepts           : {len(concepts)}")

    qid_count = sum(1 for c in concepts if list(g.objects(c, DC.identifier)))
    print(f"With dc:identifier : {qid_count}")
    print(f"Without            : {len(concepts) - qid_count}")

    schemes = list(g.subjects(RDF.type, SKOS.ConceptScheme))
    if schemes:
        print(f"\nConceptScheme : {local_name(schemes[0])} ✓")
    else:
        print("\nERROR: No skos:ConceptScheme found")
        ok = False

    top = list(g.subjects(SKOS.topConceptOf, None))
    if top:
        print(f"Top concept   : {local_name(top[0])} ✓")
    else:
        print("ERROR: No skos:topConceptOf found")
        ok = False

    missing_scheme = [c for c in concepts if not list(g.objects(c, SKOS.inScheme))]
    if missing_scheme:
        print(f"\nERROR: {len(missing_scheme)} concepts missing skos:inScheme:")
        for c in missing_scheme:
            print(f"  - {local_name(c)}")
        ok = False
    else:
        print(f"\nAll {len(concepts)} concepts have skos:inScheme ✓")

    root_name = local_name(top[0]) if top else "Tourism"
    missing_broader = [
        c for c in concepts
        if local_name(c) != root_name and not list(g.objects(c, SKOS.broader))
    ]
    if missing_broader:
        print(f"ERROR: {len(missing_broader)} non-root concepts missing skos:broader:")
        for c in missing_broader:
            print(f"  - {local_name(c)}")
        ok = False
    else:
        print(f"All non-root concepts have skos:broader ✓")

    bad_broader = []
    for c in concepts:
        for broader in g.objects(c, SKOS.broader):
            if (broader, RDF.type, SKOS.Concept) not in g:
                bad_broader.append((local_name(c), local_name(broader)))
    if bad_broader:
        print(f"ERROR: {len(bad_broader)} broken skos:broader links:")
        for child, parent in bad_broader:
            print(f"  - {child} → {parent} (target not declared as skos:Concept)")
        ok = False
    else:
        print(f"All skos:broader links resolve ✓")

    struct_rels = [
        TRAVEL.within_chunk, TRAVEL.follows_lexically,
        TRAVEL.co_occurs_with, TRAVEL.compound_elem_of,
    ]
    found_struct = sum(1 for r in struct_rels if (r, RDFS.domain, None) in g)
    if found_struct == 4:
        print(f"Structural relations : 4/4 ✓")
    else:
        print(f"WARNING: Only {found_struct}/4 structural relations found")
        ok = False

    sem_rels = list(g.subjects(RDF.type, TRAVEL.relation))
    print(f"ObjectProperties     : {len(sem_rels)}")

    print("\nConcepts per branch:")
    branch_sizes: dict[str, list] = defaultdict(list)
    for c in concepts:
        branch_sizes[get_branch(g, c)].append(local_name(c))
    for branch, members in sorted(branch_sizes.items()):
        print(f"  {branch:25s}: {len(members):2d}")

    print("\n" + ("✓ VALIDATION PASSED" if ok else "✗ VALIDATION FAILED"))
    print("=" * 60)
    return ok


def build_hierarchy_graph(g: Graph) -> nx.DiGraph:
    dg = nx.DiGraph()
    concepts = list(g.subjects(RDF.type, SKOS.Concept))
    for c in concepts:
        dg.add_node(local_name(c))
    for c in concepts:
        for broader in g.objects(c, SKOS.broader):
            dg.add_edge(local_name(broader), local_name(c), kind="broader")
    return dg


def get_object_properties(g: Graph) -> list[tuple[str, str, str]]:
    """Return list of (domain, range, property_name) for all ObjectProperties."""
    triples = []
    for rel in g.subjects(RDF.type, TRAVEL.relation):
        domains = list(g.objects(rel, RDFS.domain))
        ranges = list(g.objects(rel, RDFS.range))
        if domains and ranges:
            triples.append((
                local_name(domains[0]),
                local_name(ranges[0]),
                local_name(rel),
            ))
    return triples


def visualize_pyvis(g: Graph, dg: nx.DiGraph, output_path: Path):
    branch_map = {local_name(c): get_branch(g, c) for c in g.subjects(RDF.type, SKOS.Concept)}
    color_map = {name: BRANCH_COLORS.get(branch, "#BDC3C7") for name, branch in branch_map.items()}
    qid_nodes = {local_name(s) for s in g.subjects(DC.identifier, None)}
    branches = {local_name(c) for c in g.objects(TRAVEL.Tourism, None)
                if (c, RDF.type, SKOS.Concept) in g}
    obj_props = get_object_properties(g)

    net = Network(
        height="960px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#222222",
        heading="Travel AI — Domain Ontology Schema",
    )
    net.set_options("""{
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 180,
          "springConstant": 0.04,
          "damping": 0.09
        }
      },
      "edges": {
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.6 } },
        "font": { "size": 9, "align": "middle", "color": "#555555" },
        "width": 1.2,
        "smooth": { "type": "dynamic" }
      },
      "nodes": {
        "shape": "box",
        "borderWidth": 1,
        "font": { "size": 12, "face": "arial" }
      },
      "interaction": { "hover": true, "tooltipDelay": 100 }
    }""")

    for node in dg.nodes():
        color = color_map.get(node, "#EEEEEE")
        has_qid = node in qid_nodes
        border = "#888888"
        size = 40 if node == "Tourism" else (28 if node in branches else 20)
        title = f"<b>{node}</b><br>{'✓ QID' if has_qid else '— no QID'}<br>branch: {branch_map.get(node, '?')}"
        net.add_node(
            node,
            label=node,
            color={"background": color, "border": border},
            size=size,
            title=title,
            font={"size": 14 if node == "Tourism" else (12 if node in branches else 10)},
        )

    # Hierarchy edges — "is subclass of"
    for parent, child in dg.edges():
        net.add_edge(parent, child, label="is subclass of", color="#aaaaaa", width=1.0)

    # ObjectProperty edges — labeled with property name
    for domain, range_, prop in obj_props:
        if domain in dg.nodes() and range_ in dg.nodes():
            net.add_edge(domain, range_, label=prop, color="#E67E22", width=1.5, dashes=True)

    net.save_graph(str(output_path))
    print(f"\nVisualization → {output_path}")
    print(f"  Nodes: {dg.number_of_nodes()}, Hierarchy edges: {dg.number_of_edges()}, ObjectProperty edges: {len(obj_props)}")


def main():
    g = Graph()
    try:
        g.parse(str(TTL_PATH), format="turtle")
        print(f"Parsed {TTL_PATH.name} ✓\n")
    except Exception as exc:
        print(f"PARSE ERROR: {exc}")
        sys.exit(1)

    ok = run_tests(g)
    dg = build_hierarchy_graph(g)

    out_html = ONTOLOGY_DIR / "schema_visualization.html"
    visualize_pyvis(g, dg, out_html)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
