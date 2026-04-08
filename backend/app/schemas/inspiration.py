from pydantic import BaseModel, Field
from typing import Optional


# ── Inbound ──────────────────────────────────────────────────────────────────

class InspirationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


# ── LLM structured output (mirrors the JSON the LLM must return) ─────────────

class DestinationCard(BaseModel):
    name: str                       # e.g. "Hội An"
    country: str
    highlight: str                  # one-sentence hook
    best_for: list[str]             # ["couples", "foodies"]


class InspirationPayload(BaseModel):
    overview: str                   # 2-3 sentence intro about the destination/theme
    destinations: list[DestinationCard]
    best_time_to_visit: str         # e.g. "November – March (dry season)"
    budget_usd_per_day: dict        # {"budget": 40, "mid": 100, "luxury": 250}
    suggested_days: int             # recommended trip length
    follow_up_questions: list[str]  # 3 questions to guide next AI turn


# ── Outbound ─────────────────────────────────────────────────────────────────

class InspirationResponse(BaseModel):
    identity: str                   # resolved id (user_id or session_id)
    cache_hit: bool                 # was this served from Redis cache?
    data: InspirationPayload