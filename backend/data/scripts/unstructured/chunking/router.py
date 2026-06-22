"""
Strategy router.
Maps (source, text_type, file_type) → chunking strategy function.
Applies cleaning, chunking, and optional overlap in sequence.

Returns list of enriched chunk dicts ready for chunks.jsonl output.
"""
from .clean import clean_text
from .strategies import fixed_size, structural, semantic, table_serialize, add_overlap


# ── Strategy routing table ────────────────────────────────────────────────────
# Key: (source, text_type)  →  (strategy_fn, use_overlap)
# Wildcard "*" matches any value.

_ROUTE_TABLE: list[tuple[tuple, str, bool]] = [
    # (source,      text_type)       strategy      overlap
    ( ("cultural",  "respect"),      "structural",  True  ),
    ( ("cultural",  "laws"),         "structural",  True  ),
    ( ("safety",    "safe"),         "structural",  True  ),
    ( ("cuisine",   "eat"),          "fixed",       True  ),
    ( ("practical", "practical"),    "semantic",    True  ),
    # PDF/DOCX/HTML table sub-types → always table serialization
    ( ("*",         "*_table"),      "table",       False ),
    # image types → fixed (text already extracted by handler)
    ( ("*",         "image_*"),      "fixed",       False ),
    # default fallback
    ( ("*",         "*"),            "fixed",       True  ),
]


def _match(pattern: tuple, source: str, text_type: str) -> bool:
    src_pat, type_pat = pattern
    src_ok  = src_pat  == "*" or src_pat  == source
    type_ok = (
        type_pat == "*"
        or type_pat == text_type
        or (type_pat.endswith("*") and text_type.startswith(type_pat[:-1]))
        or (type_pat.startswith("*") and text_type.endswith(type_pat[1:]))
    )
    return src_ok and type_ok


def resolve_strategy(source: str, text_type: str) -> tuple[str, bool]:
    """Return (strategy_name, use_overlap) for a given source + text_type."""
    for pattern, strategy, overlap in _ROUTE_TABLE:
        if _match(pattern, source, text_type):
            return strategy, overlap
    return "fixed", True


# ── Main routing function ─────────────────────────────────────────────────────

def route_and_chunk(
    raw_doc: dict,
    chunk_size: int = 250,
    semantic_threshold: float = 0.45,
) -> list[dict]:
    """
    Given a raw document dict (from a handler), clean it, apply the
    correct strategy, optionally add overlap, then attach all metadata.

    Returns list of enriched chunk dicts.
    """
    text      = raw_doc["text"]
    source    = raw_doc.get("source",    "")
    text_type = raw_doc.get("text_type", "")
    file_type = raw_doc.get("file_type", "csv")

    strategy_name, use_overlap = resolve_strategy(source, text_type)

    # ── Clean ─────────────────────────────────────────────────────────────────
    preserve = strategy_name in ("structural", "table")
    cleaned  = clean_text(text, preserve_structure=preserve)
    if not cleaned:
        return []

    # ── Chunk ─────────────────────────────────────────────────────────────────
    if strategy_name == "structural":
        chunks = structural(cleaned, chunk_size)

    elif strategy_name == "semantic":
        chunks = semantic(cleaned, threshold=semantic_threshold, chunk_size=chunk_size)

    elif strategy_name == "table" or file_type.endswith("_table"):
        # table rows already pipe-delimited by handler
        rows   = [r for r in cleaned.splitlines() if r.strip()]
        chunks = table_serialize(rows)

    else:  # fixed (default)
        chunks = fixed_size(cleaned, chunk_size)

    # ── Overlap ───────────────────────────────────────────────────────────────
    if use_overlap and len(chunks) > 1:
        chunks = add_overlap(chunks)

    # ── Propagate header context from handler (DOCX/HTML) ────────────────────
    handler_ctx = raw_doc.get("_header_context", {})
    for chunk in chunks:
        if not chunk.get("header_context") and handler_ctx:
            chunk["header_context"] = handler_ctx

    # ── Attach source metadata ────────────────────────────────────────────────
    for chunk in chunks:
        chunk["destination_id"]   = raw_doc.get("destination_id",   "")
        chunk["destination_name"] = raw_doc.get("destination_name", "")
        chunk["source"]           = source
        chunk["text_type"]        = text_type
        chunk["file_type"]        = file_type
        chunk["char_len"]         = len(chunk["text"])

    return chunks
