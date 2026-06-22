#!/usr/bin/env python3
"""
Part 3 — Step 02: Embed chunks and store in LanceDB.

Input:
  - data/output/chunks.jsonl

Output:
  - data/lancedb/  (LanceDB vector store, table: "chunk")

Each LanceDB record:
  uid, chunk_id, destination_id, destination_name, source, text_type,
  strategy, has_overlap, header_context, char_len,
  text, vector (384-dim)

New fields vs original:
  strategy       — chunking strategy used (fixed/structural/semantic/table)
  has_overlap    — whether chunk includes tail of previous chunk
  header_context — nearest heading(s) from source document (JSON string)
  char_len       — character length of text

Model: sentence-transformers all-MiniLM-L6-v2  (384-dim, CPU-friendly)
Batch size: 128 chunks per encode call.
"""
import json
import pathlib
import time

import lancedb
import numpy as np
import pyarrow as pa
from sentence_transformers import SentenceTransformer

ROOT       = pathlib.Path(__file__).parents[3]
CHUNKS_IN  = ROOT / "data" / "output" / "chunks.jsonl"
LANCEDB_URI = str(ROOT / "data" / "lancedb")

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 128
TABLE_NAME = "chunk"
VECTOR_DIM = 384


def load_chunks(path: pathlib.Path) -> list[dict]:
    chunks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def main() -> None:
    t0 = time.time()
    print("=== Step 02 — Embed & Store ===\n")

    # ── Load chunks ───────────────────────────────────────────────────────────
    print(f"  Loading {CHUNKS_IN.name} …")
    chunks = load_chunks(CHUNKS_IN)
    print(f"  {len(chunks):,} chunks loaded\n")

    # ── Load model ────────────────────────────────────────────────────────────
    print(f"  Loading model: {MODEL_NAME} …")
    model = SentenceTransformer(MODEL_NAME)
    print(f"  Model ready  ({time.time()-t0:.0f}s)\n")

    # ── Embed in batches ─────────────────────────────────────────────────────
    print(f"  Embedding {len(chunks):,} chunks (batch={BATCH_SIZE}) …")
    texts = [c["text"] for c in chunks]
    vectors = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    print(f"  Embedded  shape={vectors.shape}  ({time.time()-t0:.0f}s)\n")

    # ── Build PyArrow table ───────────────────────────────────────────────────
    print("  Building PyArrow table …")
    schema = pa.schema([
        pa.field("uid",              pa.int64()),
        pa.field("chunk_id",         pa.int64()),
        pa.field("destination_id",   pa.string()),
        pa.field("destination_name", pa.string()),
        pa.field("source",           pa.string()),
        pa.field("text_type",        pa.string()),
        pa.field("strategy",         pa.string()),
        pa.field("has_overlap",      pa.bool_()),
        pa.field("header_context",   pa.string()),   # JSON-encoded dict
        pa.field("char_len",         pa.int32()),
        pa.field("text",             pa.string()),
        pa.field("vector",           pa.list_(pa.float32(), VECTOR_DIM)),
    ])

    table = pa.table(
        {
            "uid":              list(range(len(chunks))),
            "chunk_id":         [c["chunk_id"] for c in chunks],
            "destination_id":   [c["destination_id"] for c in chunks],
            "destination_name": [c["destination_name"] for c in chunks],
            "source":           [c["source"] for c in chunks],
            "text_type":        [c["text_type"] for c in chunks],
            "strategy":         [c.get("strategy", "fixed") for c in chunks],
            "has_overlap":      [bool(c.get("has_overlap", False)) for c in chunks],
            "header_context":   [json.dumps(c.get("header_context", {})) for c in chunks],
            "char_len":         [int(c.get("char_len", len(c["text"]))) for c in chunks],
            "text":             [c["text"] for c in chunks],
            "vector":           [v.tolist() for v in vectors],
        },
        schema=schema,
    )

    # ── Write to LanceDB ─────────────────────────────────────────────────────
    print(f"  Writing to LanceDB at {LANCEDB_URI} …")
    db = lancedb.connect(LANCEDB_URI)

    # overwrite if exists
    if TABLE_NAME in db.table_names():  # noqa: deprecated but still works in 0.33
        db.drop_table(TABLE_NAME)

    tbl = db.create_table(TABLE_NAME, data=table, schema=schema)

    # create vector index for ANN search
    print("  Creating vector index …")
    tbl.create_index(
        metric="cosine",
        vector_column_name="vector",
    )

    n = tbl.count_rows()
    print(f"\n  {n:,} records in table '{TABLE_NAME}'")
    print(f"  → {LANCEDB_URI}")
    print(f"  Done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
