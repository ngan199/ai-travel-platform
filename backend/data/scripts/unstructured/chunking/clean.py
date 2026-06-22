"""
Text cleaning utilities.
Handles wiki markup, HTML, unicode artefacts, and whitespace normalisation.
Preserves list markers as structural signals for detect.py.
"""
import re
import unicodedata


# ── Wiki markup ───────────────────────────────────────────────────────────────

_WIKI_LINK      = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")   # [[link|label]] → label
_WIKI_TEMPLATE  = re.compile(r"\{\{[^}]*\}\}")                      # {{template}}
_WIKI_THUMB     = re.compile(r"(?i)thumb\|[^|]*\|?")               # thumb|caption|
_WIKI_FILE      = re.compile(r"(?i)File:[^\s]+")                    # File:name
_WIKI_HEADING   = re.compile(r"={2,6}([^=]+)={2,6}")               # ==Section== → Section
_WIKI_BOLD_ITL  = re.compile(r"'{2,3}([^']+)'{2,3}")               # '''bold''' → bold
_WIKI_HR        = re.compile(r"^-{4,}$", re.MULTILINE)             # ---- horizontal rule

# ── HTML ─────────────────────────────────────────────────────────────────────

_HTML_TAG       = re.compile(r"<[^>]+>")
_HTML_ENTITY    = re.compile(r"&[a-zA-Z]+;|&#\d+;")

# ── Unicode noise ─────────────────────────────────────────────────────────────

_ZERO_WIDTH     = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")   # zero-width chars
_BULLETS_NORM   = re.compile(r"^[•·▪▸►‣⁃]\s*", re.MULTILINE)        # fancy bullets → *

# ── Whitespace ────────────────────────────────────────────────────────────────

_MULTI_SPACE    = re.compile(r"[ \t]+")
_MULTI_NEWLINE  = re.compile(r"\n{3,}")


def clean_wiki(text: str) -> str:
    """Strip wiki markup, preserving readable text and list structure."""
    text = _WIKI_LINK.sub(r"\1", text)
    text = _WIKI_TEMPLATE.sub("", text)
    text = _WIKI_THUMB.sub("", text)
    text = _WIKI_FILE.sub("", text)
    text = _WIKI_HEADING.sub(r"\1", text)
    text = _WIKI_BOLD_ITL.sub(r"\1", text)
    text = _WIKI_HR.sub("", text)
    return text


def clean_html(text: str) -> str:
    """Strip HTML tags and decode common entities."""
    text = _HTML_TAG.sub("", text)
    text = _HTML_ENTITY.sub(" ", text)
    return text


def clean_unicode(text: str) -> str:
    """Remove zero-width chars, normalise fancy bullets to ASCII *."""
    text = _ZERO_WIDTH.sub("", text)
    text = _BULLETS_NORM.sub("* ", text)
    # NFC normalisation
    text = unicodedata.normalize("NFC", text)
    return text


def clean_whitespace(text: str, *, preserve_newlines: bool = True) -> str:
    """
    Normalise whitespace.
    If preserve_newlines=True, collapse runs of 3+ newlines to 2
    (keeps paragraph/list structure for detect.py).
    If False, collapse everything to single spaces.
    """
    text = _MULTI_SPACE.sub(" ", text)
    if preserve_newlines:
        text = _MULTI_NEWLINE.sub("\n\n", text)
    else:
        text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str, *, preserve_structure: bool = True) -> str:
    """
    Full cleaning pipeline.
    preserve_structure=True keeps newlines so detect.py can read structure.
    preserve_structure=False collapses to flat prose (for fixed-size strategy).
    """
    text = clean_wiki(text)
    text = clean_html(text)
    text = clean_unicode(text)
    text = clean_whitespace(text, preserve_newlines=preserve_structure)
    return text
