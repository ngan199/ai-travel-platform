"""
Chunking strategies.

  fixed_size      — sentence-boundary greedy bucket (~250 chars)
  structural      — respect document structure (bullets, headers, tables)
  semantic        — split on cosine similarity drop between sentences
  table_serialize — convert table rows to self-contained sentences
  add_overlap     — post-process: prepend tail of previous chunk

Each strategy returns list[dict] with at minimum:
  {"text": str, "strategy": str, "header_context": dict, "has_overlap": bool}
"""
import re
from typing import Optional

from .detect import Line, Tag, detect_lines, extract_tables

CHUNK_SIZE   = 250    # target characters
MIN_CHUNK    = 20     # drop chunks shorter than this
OVERLAP_CHARS = 60    # characters to prepend from previous chunk


# ── Shared helpers ────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _flush(bucket: list[str], strategy: str, header_context: dict) -> dict:
    return {
        "text":           " ".join(bucket),
        "strategy":       strategy,
        "header_context": dict(header_context),
        "has_overlap":    False,
    }


# ── Strategy 1: Fixed-size ────────────────────────────────────────────────────

def fixed_size(
    text: str,
    chunk_size: int = CHUNK_SIZE,
) -> list[dict]:
    """
    Greedy sentence-boundary packing into ~chunk_size character buckets.
    Never splits mid-sentence.
    """
    sentences = _split_sentences(text)
    chunks: list[dict] = []
    bucket: list[str] = []
    bucket_len = 0

    for sent in sentences:
        n = len(sent)
        if bucket_len + n > chunk_size and bucket:
            chunks.append(_flush(bucket, "fixed", {}))
            bucket = [sent]
            bucket_len = n
        else:
            bucket.append(sent)
            bucket_len += n + 1

    if bucket:
        chunks.append(_flush(bucket, "fixed", {}))

    return [c for c in chunks if len(c["text"]) >= MIN_CHUNK]


# ── Strategy 2: Structure-based ───────────────────────────────────────────────

def structural(
    text: str,
    chunk_size: int = CHUNK_SIZE,
) -> list[dict]:
    """
    Split on structural boundaries (bullets, numbered items, paragraphs).
    Headers become metadata attached to subsequent chunks.
    Tables are handled inline via table_serialize.
    Short fragments are greedily merged up to chunk_size.
    """
    lines      = detect_lines(text)
    chunks:    list[dict] = []
    bucket:    list[str]  = []
    bucket_len = 0
    header_ctx: dict[str, str] = {}   # {h1: ..., h2: ..., ...}

    def flush_bucket():
        nonlocal bucket, bucket_len
        if bucket:
            merged = " ".join(bucket)
            if len(merged) >= MIN_CHUNK:
                chunks.append(_flush(bucket, "structural", header_ctx))
            bucket = []
            bucket_len = 0

    # detect table blocks first — process as serialized rows
    table_blocks = extract_tables(lines)
    table_line_ranges = {
        idx
        for start, end, _ in table_blocks
        for idx in range(start, end)
    }
    # serialize each table block
    table_chunks_by_start = {}
    for start, end, rows in table_blocks:
        table_chunks_by_start[start] = table_serialize(rows)

    i = 0
    while i < len(lines):
        line = lines[i]

        # table block start — flush bucket, emit table chunks, skip range
        if i in table_chunks_by_start:
            flush_bucket()
            for tc in table_chunks_by_start[i]:
                tc["header_context"] = dict(header_ctx)
                chunks.append(tc)
            # advance past table
            block_end = next(end for start, end, _ in table_blocks if start == i)
            i = block_end
            continue

        # skip lines already consumed by table
        if i in table_line_ranges:
            i += 1
            continue

        if line.tag == Tag.BLANK:
            # blank line = paragraph break → flush
            flush_bucket()

        elif line.tag == Tag.HEADER:
            # flush current bucket, update header context
            flush_bucket()
            level_key = f"h{line.level}"
            header_ctx[level_key] = line.text
            # clear deeper levels
            for k in list(header_ctx):
                if k.startswith("h") and int(k[1:]) > line.level:
                    del header_ctx[k]

        elif line.tag in (Tag.BULLET, Tag.NUMBERED):
            # each list item is a candidate fragment
            item_text = line.text
            n = len(item_text)
            if bucket_len + n > chunk_size and bucket:
                flush_bucket()
            bucket.append(item_text)
            bucket_len += n + 1

        elif line.tag == Tag.PARAGRAPH:
            # prose: sentence-split then pack
            for sent in _split_sentences(line.text):
                n = len(sent)
                if bucket_len + n > chunk_size and bucket:
                    flush_bucket()
                bucket.append(sent)
                bucket_len += n + 1

        i += 1

    flush_bucket()
    return chunks


# ── Strategy 3: Semantic ──────────────────────────────────────────────────────

_semantic_model = None

def _get_model():
    global _semantic_model
    if _semantic_model is None:
        from sentence_transformers import SentenceTransformer
        _semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _semantic_model


def semantic(
    text: str,
    threshold: float = 0.45,
    chunk_size: int = CHUNK_SIZE,
) -> list[dict]:
    """
    Split where cosine similarity between adjacent sentence embeddings
    drops below threshold (topic shift detected).
    Falls back to fixed_size if fewer than 3 sentences.
    """
    import numpy as np

    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return fixed_size(text, chunk_size)

    model       = _get_model()
    embeddings  = model.encode(sentences, normalize_embeddings=True, show_progress_bar=False)

    chunks: list[dict] = []
    bucket: list[str]  = [sentences[0]]

    for i in range(1, len(sentences)):
        sim = float(np.dot(embeddings[i - 1], embeddings[i]))
        n   = len(sentences[i])

        # split condition: topic shift OR bucket too long
        if sim < threshold or sum(len(s) for s in bucket) + n > chunk_size * 1.5:
            merged = " ".join(bucket)
            if len(merged) >= MIN_CHUNK:
                chunks.append({
                    "text":           merged,
                    "strategy":       "semantic",
                    "header_context": {},
                    "has_overlap":    False,
                    "sim_score":      round(sim, 3),
                })
            bucket = [sentences[i]]
        else:
            bucket.append(sentences[i])

    if bucket:
        merged = " ".join(bucket)
        if len(merged) >= MIN_CHUNK:
            chunks.append({
                "text":           merged,
                "strategy":       "semantic",
                "header_context": {},
                "has_overlap":    False,
                "sim_score":      None,
            })

    return chunks


# ── Strategy 4: Table serialization ──────────────────────────────────────────

def table_serialize(rows: list[str]) -> list[dict]:
    """
    Convert table rows to self-contained sentences.
    First row = headers.  Each subsequent row = one chunk.

    Input rows are pipe-delimited strings: "col1 | col2 | col3"
    Output: "col1: val1. col2: val2. col3: val3."
    """
    if len(rows) < 2:
        return []

    headers = [h.strip() for h in rows[0].split("|")]
    chunks:  list[dict] = []

    for row in rows[1:]:
        cells = [c.strip() for c in row.split("|")]
        pairs = [
            f"{h}: {v}"
            for h, v in zip(headers, cells)
            if h and v and v not in ("-", "—", "")
        ]
        if not pairs:
            continue
        sentence = ". ".join(pairs) + "."
        if len(sentence) >= MIN_CHUNK:
            chunks.append({
                "text":           sentence,
                "strategy":       "table",
                "header_context": {},
                "has_overlap":    False,
            })

    return chunks


# ── Post-processor: Sliding overlap ──────────────────────────────────────────

def add_overlap(
    chunks: list[dict],
    overlap_chars: int = OVERLAP_CHARS,
) -> list[dict]:
    """
    Prepend the last `overlap_chars` characters of the previous chunk
    to the current chunk, so entities near boundaries appear in both.
    Marks added chunks with has_overlap=True.
    Table and image chunks are excluded from overlap (self-contained).
    """
    result: list[dict] = []

    for i, chunk in enumerate(chunks):
        if i == 0 or chunk["strategy"] in ("table", "image"):
            result.append(chunk)
            continue

        prev = result[i - 1]
        if prev["strategy"] in ("table", "image"):
            result.append(chunk)
            continue

        tail = prev["text"][-overlap_chars:].strip()
        # only prepend if tail ends mid-sentence (no terminal punctuation)
        if tail and not tail[-1] in ".!?":
            new_chunk = dict(chunk)
            new_chunk["text"]        = tail + " " + chunk["text"]
            new_chunk["has_overlap"] = True
            result.append(new_chunk)
        else:
            result.append(chunk)

    return result
