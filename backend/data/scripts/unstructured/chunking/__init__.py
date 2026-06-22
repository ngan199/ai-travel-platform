"""
Chunking package — multi-strategy document chunking pipeline.

Usage:
    from chunking.handlers import handle_csv
    from chunking.router   import route_and_chunk
"""
from .clean      import clean_text
from .detect     import detect_lines, Tag, Line
from .strategies import fixed_size, structural, semantic, table_serialize, add_overlap
from .handlers   import handle_csv, handle_pdf, handle_docx, handle_html, handle_image
from .router     import route_and_chunk, resolve_strategy

__all__ = [
    "clean_text",
    "detect_lines", "Tag", "Line",
    "fixed_size", "structural", "semantic", "table_serialize", "add_overlap",
    "handle_csv", "handle_pdf", "handle_docx", "handle_html", "handle_image",
    "route_and_chunk", "resolve_strategy",
]
