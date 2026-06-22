"""
Per-format document handlers.
Each handler extracts (text, metadata) pairs from a source file
and returns a list of raw document dicts ready for the router.

Raw document dict:
  {
    "text":             str,
    "destination_id":   str,
    "destination_name": str,
    "source":           str,
    "text_type":        str,
    "file_type":        str,   # csv / pdf / docx / html / image
  }
"""
import csv
import json
import pathlib
import re
from typing import Iterator


# ── CSV handler ───────────────────────────────────────────────────────────────

def handle_csv(
    path: pathlib.Path,
    source: str,
    fields: list[tuple[str, str]],   # [(column_name, text_type), ...]
) -> Iterator[dict]:
    """
    Read a normalized CSV. Each row × each text column = one raw document.
    Skips rows where the text column is empty or too short (<30 chars).
    """
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dest_id   = row.get("destination_id",   "").strip()
            dest_name = row.get("destination_name", "").strip()

            for col, text_type in fields:
                raw = row.get(col, "").strip()
                if not raw or len(raw) < 30:
                    continue
                yield {
                    "text":             raw,
                    "destination_id":   dest_id,
                    "destination_name": dest_name,
                    "source":           source,
                    "text_type":        text_type,
                    "file_type":        "csv",
                }


# ── PDF handler ───────────────────────────────────────────────────────────────

def handle_pdf(
    path: pathlib.Path,
    source: str,
    text_type: str = "document",
    destination_id: str = "",
    destination_name: str = "",
) -> Iterator[dict]:
    """
    Extract text and tables from a PDF using pdfplumber.
    Each page yields one raw document. Tables are extracted separately
    as pipe-delimited strings (handled by table_serialize in strategies).
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("Install pdfplumber: pip install pdfplumber")

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # extract tables first
            for table in page.extract_tables() or []:
                if not table:
                    continue
                # convert to pipe-delimited rows
                rows = [
                    " | ".join(str(cell or "").strip() for cell in row)
                    for row in table
                    if any(cell for cell in row)
                ]
                if len(rows) >= 2:
                    yield {
                        "text":             "\n".join(rows),
                        "destination_id":   destination_id,
                        "destination_name": destination_name,
                        "source":           source,
                        "text_type":        f"{text_type}_table",
                        "file_type":        "pdf_table",
                        "_page":            page_num,
                    }

            # extract prose text (tables already removed by pdfplumber)
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            text = text.strip()
            if len(text) >= 30:
                yield {
                    "text":             text,
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        text_type,
                    "file_type":        "pdf",
                    "_page":            page_num,
                }


# ── DOCX handler ──────────────────────────────────────────────────────────────

def handle_docx(
    path: pathlib.Path,
    source: str,
    text_type: str = "document",
    destination_id: str = "",
    destination_name: str = "",
) -> Iterator[dict]:
    """
    Extract paragraphs from a DOCX with full heading-level context.
    Heading paragraphs are not emitted as content — they update the
    running header_context dict, which is injected into each content doc.
    Tables are serialized as pipe-delimited rows.
    """
    try:
        from docx import Document
        from docx.oxml.ns import qn
    except ImportError:
        raise ImportError("Install python-docx: pip install python-docx")

    doc = Document(path)
    header_ctx: dict[str, str] = {}

    def _heading_level(para) -> int | None:
        style = para.style.name or ""
        if style.startswith("Heading"):
            try:
                return int(style.split()[-1])
            except ValueError:
                return 1
        return None

    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

        # paragraph
        if tag == "p":
            from docx.text.paragraph import Paragraph
            para  = Paragraph(block, doc)
            text  = para.text.strip()
            level = _heading_level(para)

            if not text:
                continue

            if level is not None:
                # heading → update context, don't emit
                key = f"h{level}"
                header_ctx[key] = text
                for k in list(header_ctx):
                    if k.startswith("h") and int(k[1:]) > level:
                        del header_ctx[k]
            else:
                yield {
                    "text":             text,
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        text_type,
                    "file_type":        "docx",
                    "_header_context":  dict(header_ctx),
                }

        # table
        elif tag == "tbl":
            from docx.table import Table
            table = Table(block, doc)
            rows  = [
                " | ".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
                if any(cell.text.strip() for cell in row.cells)
            ]
            if len(rows) >= 2:
                yield {
                    "text":             "\n".join(rows),
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        f"{text_type}_table",
                    "file_type":        "docx_table",
                    "_header_context":  dict(header_ctx),
                }


# ── HTML handler ──────────────────────────────────────────────────────────────

def handle_html(
    path_or_html: "pathlib.Path | str",
    source: str,
    text_type: str = "document",
    destination_id: str = "",
    destination_name: str = "",
) -> Iterator[dict]:
    """
    Parse HTML using BeautifulSoup.
    Extracts h1-h6, p, ul/ol lists, and tables with heading context.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("Install beautifulsoup4: pip install beautifulsoup4")

    if isinstance(path_or_html, pathlib.Path):
        html = path_or_html.read_text(encoding="utf-8")
    else:
        html = path_or_html

    soup = BeautifulSoup(html, "html.parser")

    # remove nav/footer/script/style noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    header_ctx: dict[str, str] = {}

    for el in soup.find_all(["h1","h2","h3","h4","h5","h6","p","ul","ol","table"]):
        tag_name = el.name

        if tag_name in ("h1","h2","h3","h4","h5","h6"):
            level = int(tag_name[1])
            key   = f"h{level}"
            header_ctx[key] = el.get_text(strip=True)
            for k in list(header_ctx):
                if k.startswith("h") and int(k[1:]) > level:
                    del header_ctx[k]

        elif tag_name == "p":
            text = el.get_text(separator=" ", strip=True)
            if len(text) >= 30:
                yield {
                    "text":             text,
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        text_type,
                    "file_type":        "html",
                    "_header_context":  dict(header_ctx),
                }

        elif tag_name in ("ul", "ol"):
            items = [li.get_text(separator=" ", strip=True) for li in el.find_all("li")]
            text  = "\n".join(f"* {item}" for item in items if item)
            if len(text) >= 30:
                yield {
                    "text":             text,
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        text_type,
                    "file_type":        "html",
                    "_header_context":  dict(header_ctx),
                }

        elif tag_name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
                if any(cells):
                    rows.append(" | ".join(cells))
            if len(rows) >= 2:
                yield {
                    "text":             "\n".join(rows),
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        f"{text_type}_table",
                    "file_type":        "html_table",
                    "_header_context":  dict(header_ctx),
                }


# ── Image handler ─────────────────────────────────────────────────────────────

def handle_image(
    path: pathlib.Path,
    source: str,
    text_type: str = "image_description",
    destination_id: str = "",
    destination_name: str = "",
    *,
    use_vision_api: bool = True,
    anthropic_client=None,
) -> Iterator[dict]:
    """
    Two paths:
      use_vision_api=True  → Claude vision API describes the image
      use_vision_api=False → pytesseract OCR extracts embedded text

    For vision API, pass an initialized anthropic.Anthropic() client.
    """
    import base64

    img_bytes = path.read_bytes()
    suffix    = path.suffix.lower()
    mime_map  = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = mime_map.get(suffix, "image/jpeg")

    if use_vision_api and anthropic_client is not None:
        img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        response = anthropic_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type":  "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Describe all travel-relevant information visible in this image. "
                            "Include any text, signs, menus, maps, rules, or cultural details. "
                            "Be concise and factual."
                        ),
                    },
                ],
            }],
        )
        text = response.content[0].text.strip()
        if len(text) >= 30:
            yield {
                "text":             text,
                "destination_id":   destination_id,
                "destination_name": destination_name,
                "source":           source,
                "text_type":        "image_description",
                "file_type":        "image_vision",
            }

    else:
        # OCR fallback
        try:
            import pytesseract
            from PIL import Image as PILImage
            import io
            img = PILImage.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img, lang="eng").strip()
            if len(text) >= 30:
                yield {
                    "text":             text,
                    "destination_id":   destination_id,
                    "destination_name": destination_name,
                    "source":           source,
                    "text_type":        "image_ocr",
                    "file_type":        "image_ocr",
                }
        except Exception as e:
            print(f"  [image OCR] {path.name}: {e}")
