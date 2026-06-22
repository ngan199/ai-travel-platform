#!/usr/bin/env python3
"""
Part 3 — Step 03: NLP parse + NER + lexical graph.

For each chunk:
  1. spaCy  en_core_web_sm  → POS tags, lemmas, dependency parse, built-in NER (GPE/LOC/ORG/FAC)
  2. GLiNER gliner_small-v2.1 → zero-shot NER against travel taxonomy labels
  3. Merge spans (GLiNER takes precedence for travel-specific types)
  4. Build lexical graph (NetworkX): follows_lexically / co_occurs_with / compound_elem_of
  5. Update ent.json: populate inst[] and count for each matched entity
  6. Write entity co-occurrence sequences to ent.vec (for Word2Vec in Part 5)

Inputs:
  - data/output/chunks.jsonl
  - data/output/ent.json       (entity store from semantic layer)
  - ontology/domain.ttl        (NER label map from travel:ner_label true concepts)

Outputs:
  - data/output/lex.json       (lexical graph, NetworkX node-link)
  - data/output/ent.json       (updated entity store with inst + count)
  - data/output/ent.vec        (entity co-occurrence sequences, one line per chunk)
"""
import json
import pathlib
import re
import time
from collections import defaultdict

import networkx as nx
import spacy
from gliner import GLiNER
from rdflib import Graph, Namespace
from rdflib.namespace import SKOS

ROOT       = pathlib.Path(__file__).parents[3]
CHUNKS_IN  = ROOT / "data" / "output" / "chunks.jsonl"
ENT_IN     = ROOT / "data" / "output" / "ent.json"
DOMAIN_TTL = ROOT / "ontology" / "domain.ttl"
OUTPUT_DIR = ROOT / "data" / "output"

LEX_OUT    = OUTPUT_DIR / "lex.json"
ENT_OUT    = OUTPUT_DIR / "ent.json"       # overwrites with updated version
VEC_OUT    = OUTPUT_DIR / "ent.vec"

TRAVEL     = Namespace("https://travel-ontology.ai/vocab#")
GLINER_MODEL = "urchade/gliner_small-v2.1"
GLINER_THRESHOLD = 0.5
SPACY_MODEL = "en_core_web_sm"

# spaCy built-in NER types → travel: concept mapping
SPACY_TO_TRAVEL = {
    "GPE":     "travel:Country",    # geo-political entity
    "LOC":     "travel:Place",      # non-GPE location
    "FAC":     "travel:Venue",      # facility
    "ORG":     "travel:Hub",        # organisation (airports, stations)
    "NORP":    "travel:Knowledge",  # nationalities / groups
    "EVENT":   "travel:Event",
    "PRODUCT": "travel:Practical",
}


# ── Load NER label map from domain.ttl ───────────────────────────────────────

def load_label_map(domain_ttl: pathlib.Path) -> dict[str, str]:
    """
    Query domain.ttl for all skos:Concept with travel:ner_label true.
    Returns: {label_string: "travel:LocalName"}
    e.g. {"Country": "travel:Country", "Nation": "travel:Country", ...}
    """
    g = Graph()
    g.parse(domain_ttl, format="turtle")

    q = """
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX travel: <https://travel-ontology.ai/vocab#>
SELECT DISTINCT ?iri ?label
WHERE {
  ?iri a skos:Concept ;
    travel:ner_label true ;
    skos:prefLabel ?label .
}"""
    label_map: dict[str, str] = {}
    travel_ns = "https://travel-ontology.ai/vocab#"

    for row in g.query(q):
        iri_str    = str(row[0])
        label_str  = str(row[1])
        travel_cls = "travel:" + iri_str.replace(travel_ns, "")
        label_map[label_str] = travel_cls

    # also add altLabels
    q2 = """
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX travel: <https://travel-ontology.ai/vocab#>
SELECT DISTINCT ?iri ?alt
WHERE {
  ?iri a skos:Concept ;
    travel:ner_label true ;
    skos:altLabel ?alt .
}"""
    for row in g.query(q2):
        iri_str   = str(row[0])
        alt_str   = str(row[1])
        travel_cls = "travel:" + iri_str.replace(travel_ns, "")
        label_map[alt_str] = travel_cls

    return label_map


# ── Entity store helpers ──────────────────────────────────────────────────────

def load_ent_store(path: pathlib.Path) -> tuple[dict[str, dict], list[dict]]:
    """
    Load ent.json.
    Returns:
      lemma_index: {lemma_key → entry dict}   (mutable, for updates)
      entries:     ordered list of all entry dicts
    """
    entries: list[dict] = []
    lemma_index: dict[str, dict] = {}

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entries.append(entry)
            lemma_index[entry["lemma_key"]] = entry

    return lemma_index, entries


def save_ent_store(entries: list[dict], path: pathlib.Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Lemma key generation ──────────────────────────────────────────────────────

def make_lemma_key(text: str, nlp_doc=None) -> str:
    """
    If a spaCy doc is provided, use its lemmas.
    Otherwise fall back to simple lowercased token split.
    """
    if nlp_doc is not None:
        tokens = [t.lemma_.lower() for t in nlp_doc if not t.is_space and not t.is_punct]
    else:
        tokens = re.sub(r"[^\w\s]", "", text.lower()).split()
    return " ".join(f"NOUN.{t}" for t in tokens) if tokens else "NOUN."


# ── Span merging ─────────────────────────────────────────────────────────────

def merge_spans(
    gliner_spans: list[dict],
    spacy_ents: list,
    text: str,
) -> list[dict]:
    """
    Merge GLiNER (travel-specific) and spaCy (generic) spans.
    GLiNER takes precedence; spaCy fills gaps not covered by GLiNER.
    Each span: {text, start, end, label, travel_cls, source}
    """
    merged: list[dict] = []

    # index GLiNER spans by character range
    gliner_ranges: set[tuple[int, int]] = set()
    for sp in gliner_spans:
        merged.append({
            "text":       sp["text"],
            "start":      sp["start"],
            "end":        sp["end"],
            "label":      sp["label"],
            "travel_cls": sp.get("travel_cls", "travel:Place"),
            "source":     "gliner",
        })
        gliner_ranges.add((sp["start"], sp["end"]))

    # add spaCy spans that don't overlap with GLiNER
    for ent in spacy_ents:
        overlaps = any(
            not (ent.end_char <= gs or ent.start_char >= ge)
            for gs, ge in gliner_ranges
        )
        if not overlaps and ent.label_ in SPACY_TO_TRAVEL:
            merged.append({
                "text":       ent.text,
                "start":      ent.start_char,
                "end":        ent.end_char,
                "label":      ent.label_,
                "travel_cls": SPACY_TO_TRAVEL[ent.label_],
                "source":     "spacy",
            })

    return merged


# ── Lexical graph helpers ─────────────────────────────────────────────────────

FOLLOWS   = "travel:follows_lexically"
CO_OCCURS = "travel:co_occurs_with"
COMPOUND  = "travel:compound_elem_of"


def add_lex_edges(
    graph: nx.MultiDiGraph,
    span_lemmas: list[str],
    chunk_id: int,
) -> None:
    """
    Add lexical graph edges for the extracted entities in one chunk.
      - follows_lexically: consecutive entity pairs in sequence
      - co_occurs_with:    all pairs in the same chunk
    """
    n = len(span_lemmas)
    if n == 0:
        return

    # ensure all nodes exist
    for lk in span_lemmas:
        if not graph.has_node(lk):
            graph.add_node(lk, count=0, rank=0.0, inst=[])
        graph.nodes[lk]["count"] = graph.nodes[lk].get("count", 0) + 1
        graph.nodes[lk]["inst"] = graph.nodes[lk].get("inst", []) + [chunk_id]

    # follows_lexically: sequential pairs
    for i in range(n - 1):
        a, b = span_lemmas[i], span_lemmas[i + 1]
        if a != b:
            graph.add_edge(a, b, key=FOLLOWS, weight=1)

    # co_occurs_with: all pairs in chunk
    for i in range(n):
        for j in range(i + 1, n):
            a, b = span_lemmas[i], span_lemmas[j]
            if a != b:
                graph.add_edge(a, b, key=CO_OCCURS, weight=1)
                graph.add_edge(b, a, key=CO_OCCURS, weight=1)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    print("=== Step 03 — Parse + NER ===\n")

    # ── Load assets ───────────────────────────────────────────────────────────
    print("[1/6] Loading NER label map from domain.ttl …")
    label_map = load_label_map(DOMAIN_TTL)
    gliner_labels = list(label_map.keys())
    print(f"      {len(gliner_labels)} NER labels: {gliner_labels[:8]} …\n")

    print("[2/6] Loading entity store …")
    lemma_index, ent_entries = load_ent_store(ENT_IN)
    print(f"      {len(ent_entries):,} entries loaded\n")

    print("[3/6] Loading spaCy model …")
    nlp = spacy.load(SPACY_MODEL)
    print(f"      spaCy {SPACY_MODEL} ready\n")

    print("[4/6] Loading GLiNER model …")
    gliner = GLiNER.from_pretrained(GLINER_MODEL)
    print(f"      GLiNER {GLINER_MODEL} ready  ({time.time()-t0:.0f}s)\n")

    # ── Load chunks ───────────────────────────────────────────────────────────
    print("[5/6] Processing chunks …\n")
    chunks: list[dict] = []
    with CHUNKS_IN.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    print(f"      {len(chunks):,} chunks\n")

    lex_graph    = nx.MultiDiGraph()
    vec_lines:   list[str] = []          # one line per chunk: space-sep lemma keys
    ent_updates: dict[str, list[dict]] = defaultdict(list)  # lemma_key → inst list

    n_ner_total = 0
    n_gliner    = 0
    n_spacy     = 0

    for i, chunk in enumerate(chunks):
        text     = chunk["text"]
        chunk_id = chunk["chunk_id"]
        dest_id  = chunk["destination_id"]

        # ── spaCy parse ───────────────────────────────────────────────────
        doc = nlp(text)

        # ── GLiNER zero-shot NER ──────────────────────────────────────────
        try:
            raw_spans = gliner.predict_entities(
                text, gliner_labels, threshold=GLINER_THRESHOLD
            )
        except Exception:
            raw_spans = []

        gliner_spans = []
        for sp in raw_spans:
            travel_cls = label_map.get(sp["label"], "travel:Place")
            gliner_spans.append({
                "text":       sp["text"],
                "start":      sp["start"],
                "end":        sp["end"],
                "label":      sp["label"],
                "travel_cls": travel_cls,
            })
            n_gliner += 1

        # ── Merge spaCy + GLiNER spans ───────────────────────────────────
        merged = merge_spans(gliner_spans, list(doc.ents), text)
        n_spacy  += sum(1 for s in merged if s["source"] == "spacy")
        n_ner_total += len(merged)

        # ── Build lemma keys for each extracted span ──────────────────────
        span_lemmas: list[str] = []
        for sp in merged:
            span_doc = nlp(sp["text"])
            lk = make_lemma_key(sp["text"], span_doc)
            if not lk:
                continue
            span_lemmas.append(lk)

            # update entity store inst list
            ent_updates[lk].append({"chunk_id": chunk_id, "dest_id": dest_id})

        # ── Lexical graph edges ───────────────────────────────────────────
        add_lex_edges(lex_graph, span_lemmas, chunk_id)

        # ── Entity co-occurrence sequence (for Word2Vec) ──────────────────
        if span_lemmas:
            vec_lines.append(" ".join(span_lemmas))

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            print(f"      {i+1:>5,}/{len(chunks):,} chunks  |  "
                  f"{n_ner_total:,} spans  |  {elapsed:.0f}s")

    print(f"\n      Done: {len(chunks):,} chunks, "
          f"{n_ner_total:,} NER spans "
          f"(GLiNER: {n_gliner:,}, spaCy-fill: {n_spacy:,})  "
          f"({time.time()-t0:.0f}s)")

    # ── Update entity store ───────────────────────────────────────────────────
    print("\n[6/6] Updating entity store …")
    updated = 0
    new_uid  = max((e["uid"] for e in ent_entries), default=-1) + 1

    for lk, inst_list in ent_updates.items():
        if lk in lemma_index:
            entry = lemma_index[lk]
            entry["inst"] = entry.get("inst", []) + [
                {"chunk_id": it["chunk_id"]} for it in inst_list
            ]
            entry["count"] = entry.get("count", 0) + len(inst_list)
            updated += 1
        else:
            # new entity discovered in text, not in structured ER
            new_entry = {
                "span": {
                    "loc": [-1, -1], "text": lk, "span": lk.split(),
                    "label": None, "source": "NER_Extract", "iri": None,
                },
                "lemma_key": lk,
                "uid":   new_uid,
                "inst":  [{"chunk_id": it["chunk_id"]} for it in inst_list],
                "count": len(inst_list),
                "rank":  0.0,
            }
            ent_entries.append(new_entry)
            lemma_index[lk] = new_entry
            new_uid += 1

    save_ent_store(ent_entries, ENT_OUT)
    print(f"      {updated:,} existing entries updated, "
          f"{new_uid - (len(ent_entries) - len(ent_updates)):,} new entries added")
    mb = ENT_OUT.stat().st_size / 1_048_576
    print(f"      → {ENT_OUT.relative_to(ROOT)}  ({mb:.1f} MB)")

    # ── Save lexical graph ────────────────────────────────────────────────────
    print("\n  Saving lex.json …")
    with LEX_OUT.open("w", encoding="utf-8") as fp:
        fp.write(json.dumps(
            nx.node_link_data(lex_graph, edges="edges"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ))
    mb = LEX_OUT.stat().st_size / 1_048_576
    print(f"      {lex_graph.number_of_nodes():,} nodes, "
          f"{lex_graph.number_of_edges():,} edges")
    print(f"      → {LEX_OUT.relative_to(ROOT)}  ({mb:.1f} MB)")

    # ── Save entity vectors ───────────────────────────────────────────────────
    print("\n  Saving ent.vec …")
    with VEC_OUT.open("w", encoding="utf-8") as fp:
        for line in vec_lines:
            fp.write(line + "\n")
    print(f"      {len(vec_lines):,} sequence lines")
    print(f"      → {VEC_OUT.relative_to(ROOT)}")

    print(f"\n=== Done in {time.time()-t0:.0f}s ===")


if __name__ == "__main__":
    main()
