"""
Structure detector.
Scans cleaned text line-by-line and tags each line with a structural type.
Returns a list of (tag, text) tuples consumed by the structural chunking strategy.

Tags:
  HEADER    — section heading (wiki ==, #, ALL CAPS short line)
  BULLET    — unordered list item (* - •)
  NUMBERED  — ordered list item (1. 2) (a))
  TABLE_ROW — wiki/markdown table row (| delimited)
  PARAGRAPH — plain prose (fallback)
  BLANK     — empty line (structural separator)
"""
import re
from dataclasses import dataclass
from enum import Enum


class Tag(str, Enum):
    HEADER    = "HEADER"
    BULLET    = "BULLET"
    NUMBERED  = "NUMBERED"
    TABLE_ROW = "TABLE_ROW"
    PARAGRAPH = "PARAGRAPH"
    BLANK     = "BLANK"


@dataclass
class Line:
    tag:   Tag
    text:  str           # cleaned text with marker stripped
    raw:   str           # original line before stripping marker
    level: int = 0       # heading level (1-6) or list depth


# ── Detection regexes ─────────────────────────────────────────────────────────

_BLANK        = re.compile(r"^\s*$")
_WIKI_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")         # == Heading ==
_MD_HEADING   = re.compile(r"^(#{1,6})\s+(.+)$")                   # # Heading
_ALLCAPS      = re.compile(r"^[A-Z][A-Z\s\-/]{3,40}$")             # ALL CAPS (max 40)
_BULLET       = re.compile(r"^(\s*)[\*\-•]\s+(.+)$")
_NUMBERED     = re.compile(r"^(\s*)(\d+[\.\)]\s+|\([a-z]\)\s+)(.+)$")
_TABLE_ROW    = re.compile(r"^\|(?!\s*style=)(?!\s*class=).+\|?\s*$")  # | cell | cell | (skip CSS attrs)
_TABLE_HEADER = re.compile(r"^\|[-\s|:]+\|?\s*$")                     # |---|----|
_WIKI_CSS_ROW = re.compile(r"^\|[-\s]*style=|^\|[-\s]*class=|^\|-")   # wiki table formatting rows


def detect_lines(text: str) -> list[Line]:
    """
    Tag each line of text with its structural role.
    Returns list of Line objects in document order.
    """
    lines: list[Line] = []

    for raw in text.splitlines():
        stripped = raw.strip()

        # blank
        if _BLANK.match(stripped):
            lines.append(Line(Tag.BLANK, "", raw))
            continue

        # wiki heading: == Title ==
        m = _WIKI_HEADING.match(stripped)
        if m:
            level = len(m.group(1))
            lines.append(Line(Tag.HEADER, m.group(2).strip(), raw, level=level))
            continue

        # markdown heading: ## Title
        m = _MD_HEADING.match(stripped)
        if m:
            level = len(m.group(1))
            lines.append(Line(Tag.HEADER, m.group(2).strip(), raw, level=level))
            continue

        # all-caps short heading
        if _ALLCAPS.match(stripped) and len(stripped.split()) <= 6:
            lines.append(Line(Tag.HEADER, stripped, raw, level=2))
            continue

        # table separator / wiki CSS formatting rows (skip)
        if _TABLE_HEADER.match(stripped) or _WIKI_CSS_ROW.match(stripped):
            continue

        # table row
        if _TABLE_ROW.match(stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            lines.append(Line(Tag.TABLE_ROW, " | ".join(cells), raw))
            continue

        # bullet item
        m = _BULLET.match(raw)
        if m:
            depth = len(m.group(1)) // 2
            lines.append(Line(Tag.BULLET, m.group(2).strip(), raw, level=depth))
            continue

        # numbered item
        m = _NUMBERED.match(raw)
        if m:
            depth = len(m.group(1)) // 2
            lines.append(Line(Tag.NUMBERED, m.group(3).strip(), raw, level=depth))
            continue

        # default: paragraph prose
        lines.append(Line(Tag.PARAGRAPH, stripped, raw))

    return lines


def extract_tables(lines: list[Line]) -> list[tuple[int, int, list[str]]]:
    """
    Find contiguous TABLE_ROW blocks.
    Returns list of (start_idx, end_idx, [row_text, ...]).
    First row is treated as the header row.
    """
    tables = []
    i = 0
    while i < len(lines):
        if lines[i].tag == Tag.TABLE_ROW:
            j = i
            rows = []
            while j < len(lines) and lines[j].tag in (Tag.TABLE_ROW, Tag.BLANK):
                if lines[j].tag == Tag.TABLE_ROW:
                    rows.append(lines[j].text)
                j += 1
            if len(rows) >= 2:
                tables.append((i, j, rows))
            i = j
        else:
            i += 1
    return tables
