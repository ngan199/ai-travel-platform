"""
extraction_service.py — Step 2 component 1 (local, ~5 ms)

Runs the spaCy en_core_web_sm pipeline with an EntityRuler for structured
slot patterns.  No network calls — all CPU-bound, executed in a thread pool.

Extracted slots
---------------
destination  GPE / LOC entities from NER + KB alias normalisation
duration     DURATION entity (spaCy built-in) + custom CARDINAL+unit patterns
group_size   Custom GROUP patterns (solo / couple / family / N people)
budget       Custom BUDGET keyword patterns  → luxury | mid-range | budget
style        Custom STYLE keyword patterns   → beach | culture | adventure |
                                               food | nature
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import spacy
from spacy.language import Language

# ── Module-level singletons ───────────────────────────────────────────────────

_nlp: Optional[Language] = None
_alias_map: dict[str, str] = {}          # lowercase surface form → canonical name
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="spacy")

# ── Budget / style normalisation maps ────────────────────────────────────────

_BUDGET_MAP: dict[str, str] = {
    "luxury": "luxury", "luxurious": "luxury", "high-end": "luxury",
    "upscale": "luxury", "premium": "luxury", "five-star": "luxury",
    "budget": "budget", "cheap": "budget", "affordable": "budget",
    "backpacker": "budget", "economical": "budget", "frugal": "budget",
    "low-cost": "budget", "inexpensive": "budget",
    "mid-range": "mid-range", "moderate": "mid-range", "midrange": "mid-range",
    "reasonable": "mid-range", "average": "mid-range", "mid range": "mid-range",
    "middle": "mid-range",
}

_STYLE_MAP: dict[str, str] = {
    # beach
    "beach": "beach", "beaches": "beach", "coastal": "beach",
    "seaside": "beach", "swimming": "beach", "snorkeling": "beach",
    "snorkelling": "beach", "diving": "beach", "surfing": "beach",
    "sunbathing": "beach",
    # culture
    "culture": "culture", "cultural": "culture", "history": "culture",
    "historical": "culture", "heritage": "culture", "museum": "culture",
    "museums": "culture", "art": "culture", "arts": "culture",
    "temples": "culture", "monuments": "culture", "architecture": "culture",
    "ancient": "culture",
    # adventure
    "adventure": "adventure", "adventurous": "adventure", "hiking": "adventure",
    "trekking": "adventure", "trek": "adventure", "climbing": "adventure",
    "extreme": "adventure", "outdoor": "adventure", "outdoors": "adventure",
    "zip-lining": "adventure", "paragliding": "adventure",
    # food
    "food": "food", "culinary": "food", "cuisine": "food",
    "foodie": "food", "restaurant": "food", "restaurants": "food",
    "eating": "food", "gastronomy": "food", "street food": "food",
    "cooking": "food",
    # nature
    "nature": "nature", "wildlife": "nature", "safari": "nature",
    "natural": "nature", "eco": "nature", "ecotourism": "nature",
    "rainforest": "nature", "forest": "nature", "jungle": "nature",
    "mountains": "nature", "scenic": "nature", "national park": "nature",
}

# ── EntityRuler patterns ──────────────────────────────────────────────────────

def _budget_patterns() -> list[dict]:
    return [
        {"label": "BUDGET", "pattern": word}
        for word in _BUDGET_MAP
    ]


def _style_patterns() -> list[dict]:
    return [
        {"label": "STYLE", "pattern": word}
        for word in _STYLE_MAP
    ]


def _group_patterns() -> list[dict]:
    """Patterns for group size extraction."""
    return [
        # "solo" / "alone" / "just me" / "by myself"
        {"label": "GROUP", "pattern": [{"LOWER": {"IN": ["solo", "alone"]}}]},
        {"label": "GROUP", "pattern": [{"LOWER": "just"}, {"LOWER": "me"}]},
        {"label": "GROUP", "pattern": [{"LOWER": "by"}, {"LOWER": "myself"}]},
        # couple / partner / spouse
        {"label": "GROUP", "pattern": [{"LOWER": "couple"}]},
        {"label": "GROUP", "pattern": [{"LOWER": "my"}, {"LOWER": {"IN": [
            "partner", "wife", "husband", "girlfriend", "boyfriend", "spouse",
        ]}}]},
        {"label": "GROUP", "pattern": [{"LOWER": "two"}, {"LOWER": "of"}, {"LOWER": "us"}]},
        # family / kids
        {"label": "GROUP", "pattern": [{"LOWER": "family"}]},
        {"label": "GROUP", "pattern": [{"LOWER": {"IN": ["kids", "children", "child"]}}]},
        # N adults / N people / N friends
        {"label": "GROUP", "pattern": [
            {"LIKE_NUM": True},
            {"LOWER": {"IN": ["adults", "people", "persons", "friends", "colleagues", "travelers"]}},
        ]},
        {"label": "GROUP", "pattern": [
            {"LOWER": {"IN": ["two", "three", "four", "five", "six", "seven", "eight"]}},
            {"LOWER": {"IN": ["adults", "people", "persons", "friends"]}},
        ]},
        # group of N
        {"label": "GROUP", "pattern": [
            {"LOWER": "group"}, {"LOWER": "of"}, {"LIKE_NUM": True},
        ]},
    ]


def _duration_patterns() -> list[dict]:
    """Patterns for duration extraction (supplements spaCy's built-in DATE/TIME)."""
    units = ["day", "days", "week", "weeks", "night", "nights", "month", "months"]
    word_nums = ["one", "two", "three", "four", "five", "six", "seven", "eight",
                 "nine", "ten", "eleven", "twelve", "fourteen", "twenty", "thirty"]
    patterns = []
    # CARDINAL + unit
    for unit in units:
        patterns.append({"label": "DURATION", "pattern": [
            {"LIKE_NUM": True}, {"LOWER": unit},
        ]})
    # word number + unit
    for num in word_nums:
        for unit in units:
            patterns.append({"label": "DURATION", "pattern": [
                {"LOWER": num}, {"LOWER": unit},
            ]})
    # "a week / a month / a fortnight"
    for unit in ["week", "month", "fortnight"]:
        patterns.append({"label": "DURATION", "pattern": [
            {"LOWER": "a"}, {"LOWER": unit},
        ]})
    return patterns


# ── Pipeline initialisation ───────────────────────────────────────────────────

def init_nlp() -> None:
    """
    Load en_core_web_sm and attach EntityRuler for custom slot patterns.
    Called once at application startup (see main.py lifespan).
    """
    global _nlp
    if _nlp is not None:
        return

    nlp = spacy.load("en_core_web_sm")

    # Insert EntityRuler BEFORE the existing NER so our patterns take priority
    # for the slot labels while built-in NER still handles GPE/LOC/DATE.
    ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": False})
    ruler.add_patterns(
        _budget_patterns()
        + _style_patterns()
        + _group_patterns()
        + _duration_patterns()
    )
    _nlp = nlp


def set_alias_map(alias_map: dict[str, str]) -> None:
    """Called from main.py after the DB alias map is loaded."""
    global _alias_map
    _alias_map = alias_map


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalize_destination(raw: str) -> str:
    """Map surface form to canonical Destination name via KB aliases."""
    return _alias_map.get(raw.strip().lower(), raw.strip())


_DURATION_RE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|fourteen|twenty)\s+"
    r"(day|days|night|nights|week|weeks|month|months|fortnight)\b",
    re.IGNORECASE,
)


# ── Core extraction (sync — runs in thread pool) ──────────────────────────────

def _extract_sync(text: str, existing: dict) -> dict:
    """
    Run the spaCy pipeline and return a dict of *newly* extracted slot values.
    Already-filled slots (non-None in `existing`) are not overwritten.
    """
    if _nlp is None:
        raise RuntimeError("spaCy pipeline not initialised — call init_nlp() first")

    doc = _nlp(text)
    new: dict = {}

    # ── destination ──────────────────────────────────────────────────────────
    if not existing.get("destination"):
        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC"):
                new["destination"] = _normalize_destination(ent.text)
                break

    # ── duration ─────────────────────────────────────────────────────────────
    if not existing.get("duration"):
        # spaCy built-in DATE/TIME entities first
        for ent in doc.ents:
            if ent.label_ == "DURATION":
                new["duration"] = ent.text.lower()
                break
        # fallback: regex sweep
        if "duration" not in new:
            m = _DURATION_RE.search(text)
            if m:
                new["duration"] = m.group(0).lower()

    # ── group_size ───────────────────────────────────────────────────────────
    if not existing.get("group_size"):
        for ent in doc.ents:
            if ent.label_ == "GROUP":
                new["group_size"] = ent.text.lower()
                break

    # ── budget ───────────────────────────────────────────────────────────────
    if not existing.get("budget"):
        for ent in doc.ents:
            if ent.label_ == "BUDGET":
                mapped = _BUDGET_MAP.get(ent.text.lower())
                if mapped:
                    new["budget"] = mapped
                    break

    # ── style ─────────────────────────────────────────────────────────────────
    if not existing.get("style"):
        for ent in doc.ents:
            if ent.label_ == "STYLE":
                mapped = _STYLE_MAP.get(ent.text.lower())
                if mapped:
                    new["style"] = mapped
                    break

    return new


# ── Public async interface ────────────────────────────────────────────────────

async def extract_slots(text: str, existing_slots: dict) -> dict:
    """
    Async wrapper: runs _extract_sync in the thread pool so the event loop
    is never blocked by spaCy's CPU work.
    Returns only the *newly* found slot values (empty dict if nothing found).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _extract_sync, text, existing_slots)
