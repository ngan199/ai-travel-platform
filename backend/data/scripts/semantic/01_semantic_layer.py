#!/usr/bin/env python3
"""
Semantic Layer — Part 2 of the ontology pipeline.

Inputs:
  - ontology/domain.ttl           (SKOS travel taxonomy, travel: namespace)
  - data/output/er.json           (283,568 resolved entities, JSONL)

Outputs:
  - data/output/thesaurus.ttl     (RDF Turtle: taxonomy + all ER entities)
  - data/output/erkg.json         (NetworkX MultiDiGraph, node-link JSON)
  - data/output/ent.json          (Entity store, JSONL)

Design notes:
  - er.json is streamed line-by-line (338 MB — never fully loaded)
  - entity / edge data is collected in memory during the single er.json scan
    → used to build erkg.json and ent.json without large SPARQL queries
  - rdflib is used only for: domain.ttl + ER entity triples → thesaurus.ttl
  - SPARQL queries run only on the small taxonomy portion (~50 concepts)
"""
import json
import pathlib
import time

import networkx as nx
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DC, PROV, RDF, SKOS

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = pathlib.Path(__file__).parents[3]
DOMAIN_TTL = ROOT / "ontology" / "domain.ttl"
ER_JSON    = ROOT / "data" / "output" / "er.json"
OUTPUT_DIR = ROOT / "data" / "output"

THESAURUS_PATH = OUTPUT_DIR / "thesaurus.ttl"
ERKG_PATH      = OUTPUT_DIR / "erkg.json"
ENT_PATH       = OUTPUT_DIR / "ent.json"

# ── Namespaces ────────────────────────────────────────────────────────────────
TRAVEL     = Namespace("https://travel-ontology.ai/vocab#")
SZ         = Namespace("https://github.com/senzing-garage/sz-semantics/wiki/ns#")
TRAVEL_NS  = "https://travel-ontology.ai/vocab#"
SZ_NS      = "https://github.com/senzing-garage/sz-semantics/wiki/ns#"

# ── RECORD_TYPE → travel: class ───────────────────────────────────────────────
RTYPE_MAP: dict[str, URIRef] = {
    "COUNTRY":             TRAVEL.Country,
    "CITY":                TRAVEL.City,
    "REGION":              TRAVEL.Region,
    "PROVINCE":            TRAVEL.Province,
    "DISTRICT":            TRAVEL.District,
    "NEIGHBORHOOD":        TRAVEL.Neighborhood,
    "VENUE":               TRAVEL.Venue,
    "NATIONAL_PARK":       TRAVEL.Park,
    "FOOD_MARKET":         TRAVEL.Market,
    "RESTAURANT":          TRAVEL.Restaurant,
    "HOTEL":               TRAVEL.Hotel,
    "HOSTEL":              TRAVEL.Hostel,
    "RESORT":              TRAVEL.Resort,
    "GUESTHOUSE":          TRAVEL.Guesthouse,
    "VILLA":               TRAVEL.Villa,
    "CAMPING":             TRAVEL.Camping,
    "LODGING":             TRAVEL.Lodging,
    "AIRPORT":             TRAVEL.Airport,
    "PORT":                TRAVEL.Port,
    "BUS_STATION":         TRAVEL.Bus,
    "TRAIN_STATION":       TRAVEL.Train,
    "TRANSPORT_HUB":       TRAVEL.Hub,
    "FESTIVAL":            TRAVEL.Festival,
    "EVENT":               TRAVEL.Event,
    # activity subtypes without a dedicated concept → nearest parent
    "MUSEUM":              TRAVEL.Venue,
    "TOURIST_ATTRACTION":  TRAVEL.Venue,
    "BEACH":               TRAVEL.Venue,
    "ARCHAEOLOGICAL_SITE": TRAVEL.Venue,
    "RELIGIOUS_SITE":      TRAVEL.Venue,
    "AMUSEMENT_PARK":      TRAVEL.Venue,
    "WATER_PARK":          TRAVEL.Venue,
    "HIKING_AREA":         TRAVEL.Venue,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_lemma_key(name: str) -> str:
    """Simple lemma key: 'NOUN.<lowercased_token>' for each whitespace token."""
    tokens = name.lower().split()
    return " ".join(f"NOUN.{t}" for t in tokens) if tokens else "NOUN."


def abbrev(uri: str) -> str:
    """Abbreviate a full URI to a prefixed form for NetworkX node IDs."""
    if uri.startswith(TRAVEL_NS):
        return "travel:" + uri[len(TRAVEL_NS):]
    if uri.startswith(SZ_NS):
        return "sz:" + uri[len(SZ_NS):]
    return uri


# ── Step A+B: build RDF graph + collect ERKG/ent data ────────────────────────

def build_rdf_and_collect(g: Graph) -> tuple[
    list[dict],       # er_nodes
    list[tuple],      # er_edges  (src_str, dst_str, pred_str)
    dict[str, dict],  # dr_nodes  rec_short → {rec_key, data_src}
    dict[str, str],   # ds_nodes  src_short → src_id
]:
    """
    Stream er.json once:
      • add RDF triples to g (for thesaurus.ttl)
      • collect entity/edge/record data in memory (for erkg.json and ent.json)
    """
    er_nodes: list[dict] = []
    er_edges: list[tuple] = []
    dr_nodes: dict[str, dict] = {}
    ds_nodes: dict[str, str]  = {}

    seen_recs:    set[str] = set()
    seen_sources: set[str] = set()
    n = 0
    t0 = time.time()

    with ER_JSON.open("r", encoding="utf-8") as fp:
        for raw in fp:
            raw = raw.strip()
            if not raw:
                continue

            obj  = json.loads(raw)
            res  = obj["RESOLVED_ENTITY"]
            eid  = str(res["ENTITY_ID"])
            name = res["ENTITY_NAME"].replace('"', "'").strip()

            ent_uri   = SZ[eid]               # rdflib URIRef
            ent_short = f"sz:{eid}"           # NetworkX / ent.json key

            # RECORD_TYPE → travel: class
            rtype_str = ""
            for feat in res["FEATURES"].get("RECORD_TYPE", []):
                rtype_str = feat.get("FEAT_DESC", "")
            travel_cls     = RTYPE_MAP.get(rtype_str, TRAVEL.Venue)
            travel_cls_str = abbrev(str(travel_cls))  # "travel:Country" etc.

            # ── RDF: entity type + labels ────────────────────────────────
            g.add((ent_uri, RDF.type,       travel_cls))
            g.add((ent_uri, SKOS.prefLabel, Literal(name, lang="en")))

            seen_names: set[str] = {name}
            for feat in res["FEATURES"].get("NAME", []):
                for fdv in feat.get("FEAT_DESC_VALUES", []):
                    alt = fdv.get("FEAT_DESC", "").strip()
                    if alt and alt not in seen_names:
                        g.add((ent_uri, SKOS.altLabel, Literal(alt, lang="en")))
                        seen_names.add(alt)

            # ── RDF: provenance (records) ────────────────────────────────
            rec_count = 0
            for rec in res.get("RECORDS", []):
                src_id  = rec["DATA_SOURCE"].replace(" ", "_").lower()
                rec_id  = rec["RECORD_ID"]
                m_key   = rec.get("MATCH_KEY")   or "INITIAL"
                m_level = rec.get("MATCH_LEVEL_CODE") or "INITIAL"

                src_uri   = SZ[f"ds_{src_id}"]
                rec_uri   = SZ[f"ds_{src_id}_{rec_id}"]
                src_short = f"sz:ds_{src_id}"
                rec_short = f"sz:ds_{src_id}_{rec_id}"

                # blank node reification: entity ↔ record + match metadata
                bn = BNode()
                g.add((bn, RDF.subject,    ent_uri))
                g.add((bn, RDF.predicate,  SKOS.exactMatch))
                g.add((bn, RDF.object,     rec_uri))
                g.add((bn, SZ.match_key,   Literal(m_key)))
                g.add((bn, SZ.match_level, Literal(m_level)))

                g.add((ent_uri, PROV.wasDerivedFrom, rec_uri))

                if rec_short not in seen_recs:
                    g.add((rec_uri, RDF.type,           SZ.DataRecord))
                    g.add((rec_uri, DC.identifier,       Literal(rec_id)))
                    g.add((rec_uri, PROV.wasQuotedFrom,  src_uri))
                    seen_recs.add(rec_short)
                    dr_nodes[rec_short] = {"rec_key": rec_id, "data_src": src_short}

                if src_short not in seen_sources:
                    g.add((src_uri, RDF.type,     DCAT.Dataset))
                    g.add((src_uri, DC.identifier, Literal(src_id)))
                    seen_sources.add(src_short)
                    ds_nodes[src_short] = src_id

                rec_count += 1

            # ── RDF + in-memory: related entities ───────────────────────
            # (all RELATED_ENTITIES are [] in our Splink-generated er.json,
            #  but handled correctly for forward compatibility)
            for rel in obj.get("RELATED_ENTITIES", []):
                rel_id    = str(rel["ENTITY_ID"])
                rel_level = rel.get("MATCH_LEVEL_CODE", "")
                rel_pred  = (SKOS.closeMatch
                             if rel_level == "POSSIBLY_SAME"
                             else SKOS.related)
                rel_pshort = ("skos:closeMatch"
                              if rel_level == "POSSIBLY_SAME"
                              else "skos:related")
                rel_uri   = SZ[rel_id]
                rel_short = f"sz:{rel_id}"

                bn2 = BNode()
                g.add((bn2, RDF.subject,    ent_uri))
                g.add((bn2, RDF.predicate,  rel_pred))
                g.add((bn2, RDF.object,     rel_uri))
                g.add((bn2, SZ.match_key,   Literal(rel.get("MATCH_KEY", ""))))
                g.add((bn2, SZ.match_level, Literal(rel_level)))

                er_edges.append((ent_short, rel_short, rel_pshort))

            er_nodes.append({
                "iri":   ent_short,
                "class": travel_cls_str,
                "name":  name,
                "lemma": make_lemma_key(name),
                "count": rec_count,
            })

            n += 1
            if n % 50_000 == 0:
                elapsed = time.time() - t0
                print(f"    {n:>7,}  entities  |  {len(g):>9,} triples  |  {elapsed:.0f}s")

    return er_nodes, er_edges, dr_nodes, ds_nodes


# ── Step D: NetworkX ERKG backbone ───────────────────────────────────────────

def build_erkg(
    g: Graph,
    er_nodes:  list[dict],
    er_edges:  list[tuple],
    dr_nodes:  dict[str, dict],
    ds_nodes:  dict[str, str],
) -> nx.MultiDiGraph:
    """Build NetworkX MultiDiGraph from collected data + SPARQL on taxonomy."""
    graph: nx.MultiDiGraph = nx.MultiDiGraph()

    # D1: Taxonomy nodes (SPARQL on small domain.ttl portion ~50 nodes)
    q_taxo = """
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX travel: <https://travel-ontology.ai/vocab#>
SELECT DISTINCT ?iri ?label ?lemma ?defn
WHERE {
  ?iri a skos:Concept ;
    skos:prefLabel ?label ;
    travel:lemma_phrase ?lemma .
  OPTIONAL { ?iri skos:definition ?defn . }
}""".strip()
    taxo_n = 0
    for row in g.query(q_taxo):
        iri_s   = abbrev(str(row[0]))
        label_s = str(row[1])
        lemma_s = str(row[2])
        defn_s  = str(row[3]) if row[3] else ""
        graph.add_node(iri_s, kind="TAXONOMY",
                       text=label_s, lemma=lemma_s, defn=defn_s,
                       count=1, rank=0.0)
        taxo_n += 1
    print(f"    taxonomy nodes    : {taxo_n:,}")

    # D2: Taxonomy edges (skos:broader / skos:narrower / skos:related)
    q_tedge = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?src ?rel ?dst
WHERE {
  VALUES ?rel { skos:broader skos:narrower skos:related }
  ?src a skos:Concept ; ?rel ?dst .
}""".strip()
    taxo_e = 0
    for row in g.query(q_tedge):
        src_s = abbrev(str(row[0]))
        dst_s = abbrev(str(row[2]))
        rel_s = "skos:" + str(row[1]).split("#")[-1]
        graph.add_edge(src_s, dst_s, key=rel_s, prob=1.0)
        taxo_e += 1
    print(f"    taxonomy edges    : {taxo_e:,}")

    # D3: ER entity nodes + rdf:type edges (from in-memory list — no SPARQL)
    for ent in er_nodes:
        graph.add_node(ent["iri"], kind="ENTITY",
                       text=ent["name"], lemma=ent["lemma"],
                       count=ent["count"], rank=0.0)
        graph.add_edge(ent["iri"], ent["class"], key="rdf:type", prob=1.0)
    print(f"    ER entity nodes   : {len(er_nodes):,}")

    # D4: Data record nodes
    for rec_iri, rec_data in dr_nodes.items():
        graph.add_node(rec_iri, kind="DATAREC",
                       rec_key=rec_data["rec_key"],
                       data_src=rec_data["data_src"])
    print(f"    data record nodes : {len(dr_nodes):,}")

    # D5: Entity↔entity relation edges
    for src, dst, pred in er_edges:
        graph.add_edge(src, dst, key=pred, prob=0.9)
    print(f"    entity rel edges  : {len(er_edges):,}")

    return graph


# ── Step F+G: entity store ────────────────────────────────────────────────────

def write_ent_store(g: Graph, er_nodes: list[dict]) -> int:
    """Write ent.json: taxonomy concepts then ER entities."""
    uid = 0
    with ENT_PATH.open("w", encoding="utf-8") as fp:

        # F1: taxonomy concepts from SPARQL (small)
        q_taxo = """
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX travel: <https://travel-ontology.ai/vocab#>
SELECT DISTINCT ?iri ?lemma
WHERE {
  ?iri a skos:Concept ;
    travel:lemma_phrase ?lemma .
}""".strip()
        seen_lemmas: set[str] = set()
        for row in g.query(q_taxo):
            lemma = str(row[1])
            if lemma in seen_lemmas:
                continue
            seen_lemmas.add(lemma)
            fp.write(json.dumps({
                "span": {
                    "loc": [-1, -1], "text": "", "span": [],
                    "label": None, "source": "Domain_Taxonomy", "iri": None,
                },
                "lemma_key": lemma,
                "uid": uid, "inst": [], "count": 1, "rank": 0.0,
            }, ensure_ascii=False) + "\n")
            uid += 1
        taxo_total = uid
        print(f"    taxonomy entries  : {taxo_total:,}")

        # F2: ER entities (from in-memory list)
        for ent in er_nodes:
            tokens = ent["name"].split()
            fp.write(json.dumps({
                "span": {
                    "loc": [0, max(0, len(tokens) - 1)],
                    "text": ent["name"],
                    "span": tokens,
                    "label": None,
                    "source": "Entity_Resolution",
                    "iri": ent["iri"],
                },
                "lemma_key": ent["lemma"],
                "uid": uid, "inst": [], "count": ent["count"], "rank": 0.0,
            }, ensure_ascii=False) + "\n")
            uid += 1

    print(f"    ER entries        : {uid - taxo_total:,}")
    print(f"    total entries     : {uid:,}")
    return uid


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Semantic Layer ===\n")

    # ── A. Init RDF graph + load domain.ttl ──────────────────────────────
    print("[A] Loading domain.ttl …")
    g = Graph()
    g.bind("travel", TRAVEL)
    g.bind("sz",     SZ)
    g.bind("skos",   SKOS)
    g.bind("dc",     DC)
    g.bind("prov",   PROV)
    g.bind("dcat",   DCAT)
    g.bind("rdf",    RDF)
    g.parse(DOMAIN_TTL, format="turtle")
    print(f"    {len(g):,} triples (domain.ttl)\n")

    # ── B. Stream er.json → RDF + collect data ────────────────────────────
    print("[B] Streaming er.json …")
    er_nodes, er_edges, dr_nodes, ds_nodes = build_rdf_and_collect(g)
    print(f"    {len(er_nodes):,} entities  |  {len(g):,} triples  |  {time.time()-t0:.0f}s\n")

    # ── C. Serialize thesaurus.ttl ────────────────────────────────────────
    print("[C] Saving thesaurus.ttl …")
    g.serialize(destination=str(THESAURUS_PATH), format="turtle")
    mb = THESAURUS_PATH.stat().st_size / 1_048_576
    print(f"    → {THESAURUS_PATH.relative_to(ROOT)}  ({mb:.1f} MB, {time.time()-t0:.0f}s)\n")

    # ── D. Build NetworkX ERKG ────────────────────────────────────────────
    print("[D] Building ERKG …")
    graph = build_erkg(g, er_nodes, er_edges, dr_nodes, ds_nodes)
    print(f"    total: {graph.number_of_nodes():,} nodes, {graph.number_of_edges():,} edges  |  {time.time()-t0:.0f}s\n")

    # ── E. Serialize erkg.json ────────────────────────────────────────────
    print("[E] Saving erkg.json …")
    with ERKG_PATH.open("w", encoding="utf-8") as fp:
        fp.write(json.dumps(
            nx.node_link_data(graph, edges="edges"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ))
    mb = ERKG_PATH.stat().st_size / 1_048_576
    print(f"    → {ERKG_PATH.relative_to(ROOT)}  ({mb:.1f} MB, {time.time()-t0:.0f}s)\n")

    # ── F+G. Build + save ent.json ────────────────────────────────────────
    print("[F] Saving ent.json …")
    write_ent_store(g, er_nodes)
    mb = ENT_PATH.stat().st_size / 1_048_576
    print(f"    → {ENT_PATH.relative_to(ROOT)}  ({mb:.1f} MB, {time.time()-t0:.0f}s)\n")

    print(f"=== Done in {time.time()-t0:.0f}s ===")


if __name__ == "__main__":
    main()
