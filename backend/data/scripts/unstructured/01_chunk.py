#!/usr/bin/env python3
"""
Part 3 — Step 01: Multi-strategy chunking pipeline.

Strategies applied per source:
  cultural  respect / laws  → structural  + overlap   (wiki bullets + prose)
  cuisine   eat             → fixed-size  + overlap   (flowing prose)
  safety    safe            → structural  + overlap   (advisory bullet lists)
  practical practical       → semantic    + overlap   (dense mixed-topic facts)
  PDF/DOCX/HTML             → structural + table serialization + overlap
  image                     → vision API or OCR → fixed

Also discovers any PDF / DOCX / HTML / image files in data/sources/
and routes them through the appropriate handler automatically.

Inputs:
  - data/normalized/cultural_norms.csv
  - data/normalized/cuisines.csv
  - data/normalized/safety_tips.csv
  - data/normalized/practical_info.csv
  - data/sources/**  (optional: PDF, DOCX, HTML, images)

Outputs:
  - data/output/chunks.jsonl

Each chunk record:
  {
    "chunk_id":        int,
    "destination_id":  str,
    "destination_name": str,
    "source":          str,
    "text_type":       str,
    "text":            str,
    "strategy":        str,   # fixed / structural / semantic / table / image_*
    "has_overlap":     bool,
    "header_context":  dict,  # {h1,h2,...} from DOCX/HTML/wiki headings
    "char_len":        int,
  }
"""
import json
import pathlib
import sys
import time
from collections import defaultdict

# make chunking package importable from this script's directory
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from chunking.handlers import handle_csv, handle_pdf, handle_docx, handle_html, handle_image
from chunking.router   import route_and_chunk

ROOT       = pathlib.Path(__file__).parents[3]
NORM       = ROOT / "data" / "normalized"
SOURCES_DIR = ROOT / "data" / "sources"
OUTPUT_DIR = ROOT / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_OUT = OUTPUT_DIR / "chunks.jsonl"

CHUNK_SIZE          = 250
SEMANTIC_THRESHOLD  = 0.45

# ── CSV source definitions ────────────────────────────────────────────────────

CSV_SOURCES = [
    {
        "file":   NORM / "cultural_norms.csv",
        "source": "cultural",
        "fields": [
            ("respect_text",    "respect"),
            ("local_laws_text", "laws"),
        ],
    },
    {
        "file":   NORM / "cuisines.csv",
        "source": "cuisine",
        "fields": [
            ("eat_section_text", "eat"),
        ],
    },
    {
        "file":   NORM / "safety_tips.csv",
        "source": "safety",
        "fields": [
            ("stay_safe_text", "safe"),
        ],
    },
    {
        "file":   NORM / "practical_info.csv",
        "source": "practical",
        "fields": [
            ("practical_notes_text", "practical"),
        ],
    },
]

# ── File-type routing for data/sources/ ──────────────────────────────────────

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
PDF_EXTS   = {".pdf"}
DOCX_EXTS  = {".docx"}
HTML_EXTS  = {".html", ".htm"}


def iter_extra_sources():
    """
    Discover non-CSV files under data/sources/ and yield raw documents.
    Destination metadata is inferred from the parent folder name if available.
    """
    if not SOURCES_DIR.exists():
        return

    for path in sorted(SOURCES_DIR.rglob("*")):
        if not path.is_file():
            continue

        ext         = path.suffix.lower()
        dest_name   = path.parent.name if path.parent != SOURCES_DIR else ""
        dest_id     = ""
        source_name = path.stem

        if ext in PDF_EXTS:
            yield from handle_pdf(path, source=source_name,
                                  destination_name=dest_name, destination_id=dest_id)

        elif ext in DOCX_EXTS:
            yield from handle_docx(path, source=source_name,
                                   destination_name=dest_name, destination_id=dest_id)

        elif ext in HTML_EXTS:
            yield from handle_html(path, source=source_name,
                                   destination_name=dest_name, destination_id=dest_id)

        elif ext in IMAGE_EXTS:
            yield from handle_image(path, source=source_name,
                                    destination_name=dest_name, destination_id=dest_id,
                                    use_vision_api=False)   # OCR mode (no API key needed)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    print("=== Step 01 — Multi-Strategy Chunk ===\n")

    chunk_id   = 0
    stats: dict[str, dict] = defaultdict(lambda: {"docs": 0, "chunks": 0,
                                                   "strategies": defaultdict(int)})

    with CHUNKS_OUT.open("w", encoding="utf-8") as out:

        # ── CSV sources ───────────────────────────────────────────────────────
        for src_def in CSV_SOURCES:
            path   = src_def["file"]
            source = src_def["source"]
            fields = src_def["fields"]

            if not path.exists():
                print(f"  SKIP {path.name} (not found)")
                continue

            for raw_doc in handle_csv(path, source=source, fields=fields):
                stats[source]["docs"] += 1
                chunks = route_and_chunk(
                    raw_doc,
                    chunk_size=CHUNK_SIZE,
                    semantic_threshold=SEMANTIC_THRESHOLD,
                )
                for chunk in chunks:
                    record = {
                        "chunk_id":        chunk_id,
                        "destination_id":  chunk["destination_id"],
                        "destination_name": chunk["destination_name"],
                        "source":          chunk["source"],
                        "text_type":       chunk["text_type"],
                        "text":            chunk["text"],
                        "strategy":        chunk["strategy"],
                        "has_overlap":     chunk["has_overlap"],
                        "header_context":  chunk.get("header_context", {}),
                        "char_len":        chunk["char_len"],
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    chunk_id += 1
                    stats[source]["chunks"] += 1
                    stats[source]["strategies"][chunk["strategy"]] += 1

        # ── Extra sources (PDF / DOCX / HTML / image) ─────────────────────────
        extra_count = 0
        for raw_doc in iter_extra_sources():
            source = raw_doc.get("source", "extra")
            chunks = route_and_chunk(
                raw_doc,
                chunk_size=CHUNK_SIZE,
                semantic_threshold=SEMANTIC_THRESHOLD,
            )
            for chunk in chunks:
                record = {
                    "chunk_id":        chunk_id,
                    "destination_id":  chunk["destination_id"],
                    "destination_name": chunk["destination_name"],
                    "source":          chunk["source"],
                    "text_type":       chunk["text_type"],
                    "text":            chunk["text"],
                    "strategy":        chunk["strategy"],
                    "has_overlap":     chunk["has_overlap"],
                    "header_context":  chunk.get("header_context", {}),
                    "char_len":        chunk["char_len"],
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_id += 1
                extra_count += 1

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"  {'Source':<12} {'Docs':>6} {'Chunks':>7}  Strategies")
    print(f"  {'-'*12} {'-'*6} {'-'*7}  ----------")
    for source, s in stats.items():
        strat_str = "  ".join(f"{k}:{v}" for k, v in sorted(s["strategies"].items()))
        print(f"  {source:<12} {s['docs']:>6,} {s['chunks']:>7,}  {strat_str}")

    if extra_count:
        print(f"\n  extra sources (PDF/DOCX/HTML/image): {extra_count} chunks")

    total  = chunk_id
    size_kb = CHUNKS_OUT.stat().st_size // 1024
    elapsed = time.time() - t0
    print(f"\n  total: {total:,} chunks → {CHUNKS_OUT.relative_to(ROOT)}")
    print(f"  file:  {size_kb:,} KB  |  {elapsed:.0f}s")


if __name__ == "__main__":
    main()
