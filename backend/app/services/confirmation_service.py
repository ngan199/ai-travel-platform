"""
confirmation_service.py — Step 3 helpers

Three-layer confirmation detection
-----------------------------------
Layer 1  Structured output  — primary — LLM field confirmation_status
Layer 2a Reject keywords    — override — "but", "change", "actually" → pending
Layer 2b Confirm keywords   — fallback — "yes", "perfect", "go ahead" → confirmed
Layer 3  Ambiguity          — ask once more explicitly, capped at 1 re-ask

DB write
--------
On confirmed: write TripIntention to PostgreSQL in thread-pool executor.
"""

import asyncio
import uuid as uuid_lib
from typing import Optional
from uuid import UUID

from app.db.database import SessionLocal
from app.models.travel_intention import TravelIntention

# ── Keyword lists ─────────────────────────────────────────────────────────────

# Checked FIRST — any match forces "pending" regardless of LLM output.
_REJECT_SIGNALS = frozenset([
    "but", "change", "actually", "wait", "no,", "nope", "not right",
    "wrong", "different", "instead", "rather", "except", "only",
    "hmm", "not sure", "unsure", "maybe not",
])

# Checked only when no reject signal found.
_CONFIRM_SIGNALS = frozenset([
    "yes", "yeah", "yep", "yup", "correct", "right", "perfect",
    "sure", "great", "go ahead", "let's go", "lets go", "confirm",
    "confirmed", "sounds good", "looks good", "that's right",
    "that's correct", "exactly", "absolutely", "definitely",
    "ok", "okay", "cool", "awesome", "fantastic", "good to go",
])


# ── Three-layer detection ─────────────────────────────────────────────────────

def detect_confirmation(user_text: str, llm_status: str) -> str:
    """
    Returns one of: "confirmed" | "pending" | "partial" | "ambiguous"

    Decision order
    --------------
    1. Reject keywords (Layer 2a) — highest priority, overrides everything.
       "Yes but make it luxury" contains "but" → pending (not the LLM's call).
    2. LLM structured field (Layer 1) — used when no reject keyword found.
    3. Confirm keywords (Layer 2b) — fallback when LLM is inconclusive.
    4. Ambiguous — neither layer could decide.
    """
    lower = user_text.lower()
    words = set(lower.replace(",", " ").replace(".", " ").split())

    # Layer 2a: reject signals override everything
    if _REJECT_SIGNALS & words or any(p in lower for p in (
        "not right", "not sure", "maybe not", "rather than",
    )):
        # Special case: "Yes but …" might be a partial (slot update + confirm).
        # We keep this as "pending" here and let the LLM's `updated_slots`
        # propagate the change — the endpoint re-presents after merging.
        return "pending"

    # Layer 1: trust LLM structured output
    if llm_status in ("confirmed", "pending", "partial"):
        return llm_status

    # Layer 2b: confirm keyword fallback
    if _CONFIRM_SIGNALS & words or any(p in lower for p in (
        "sounds good", "looks good", "go ahead", "let's go", "good to go",
        "that's right", "that's correct",
    )):
        return "confirmed"

    # Layer 3: ambiguous
    return "ambiguous"


# ── Ambiguity re-ask ──────────────────────────────────────────────────────────

_MAX_REASK = 1   # ask at most once explicitly before treating as pending


def should_reask(slots: dict) -> bool:
    return slots.get("confirmation_reask_count", 0) < _MAX_REASK


def explicit_reask_message(slots: dict) -> str:
    """
    Produce a pre-written, no-LLM re-ask using the current slot summary.
    Formats: "Just to confirm — [summary]. Say 'yes' to confirm or tell me what to change."
    """
    parts = []
    if slots.get("destination"):
        parts.append(slots["destination"])
    if slots.get("duration"):
        parts.append(slots["duration"])
    if slots.get("group_size"):
        parts.append(slots["group_size"])
    if slots.get("budget"):
        parts.append(f"{slots['budget']} budget")
    if slots.get("style"):
        parts.append(f"{slots['style']} focus")
    summary = ", ".join(parts) if parts else "your trip details"
    return (
        f"Just to confirm — {summary}. "
        "Say 'yes' to go ahead or let me know what you'd like to change."
    )


# ── PostgreSQL write ──────────────────────────────────────────────────────────

def _parse_user_uuid(user_id_str: Optional[str]) -> Optional[UUID]:
    """Return a UUID if the string is a valid UUID, else None."""
    if not user_id_str:
        return None
    try:
        return UUID(user_id_str)
    except ValueError:
        return None


def _write_intention_sync(
    session_id: str,
    user_id_str: Optional[str],
    slots: dict,
) -> str:
    """Sync DB write — called in thread-pool executor."""
    intention_id = uuid_lib.uuid4()
    record = TravelIntention(
        intention_id=intention_id,
        session_id=session_id,
        user_id=_parse_user_uuid(user_id_str),
        destination_raw=slots["destination"],
        destination_qid=slots.get("destination_qid"),   # set by KB lookup in Step 4
        duration=slots["duration"],
        group_size=slots["group_size"],
        budget=slots["budget"],
        travel_style=slots.get("style"),
    )
    with SessionLocal() as db:
        db.add(record)
        db.commit()
    return str(intention_id)


async def save_intention(
    session_id: str,
    user_id: Optional[str],
    slots: dict,
) -> str:
    """
    Write the confirmed TravelIntention to PostgreSQL.
    Returns the new intention_id as a string.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _write_intention_sync, session_id, user_id, slots
    )
