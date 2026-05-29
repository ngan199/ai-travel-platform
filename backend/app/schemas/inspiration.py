import enum
from pydantic import BaseModel, Field
from typing import Literal, Optional


# ── Inbound ──────────────────────────────────────────────────────────────────

class InspirationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


# ── Slot state (Step 2) ───────────────────────────────────────────────────────

BudgetTier = Literal["luxury", "mid-range", "budget"]
TripStyle  = Literal["beach", "culture", "adventure", "food", "nature"]
SessionMode = Literal["slot_collection", "confirmation", "retrieval"]

class SlotState(BaseModel):
    destination: Optional[str] = None
    duration:    Optional[str] = None          # e.g. "7 days", "2 weeks"
    group_size:  Optional[str] = None          # e.g. "solo", "couple", "family with children"
    budget:      Optional[BudgetTier] = None
    style:       Optional[TripStyle] = None    # optional — inferred when possible
    mode:        SessionMode = "slot_collection"

    @property
    def required_complete(self) -> bool:
        return all([self.destination, self.duration, self.group_size, self.budget])


# ── Slot collection response (Step 2 outbound) ───────────────────────────────

class SlotChatResponse(BaseModel):
    identity:        str
    message:         str        # conversational reply shown to the user
    slots:           SlotState
    slots_complete:  bool       # True when all 4 required slots are filled
    used_llm:        bool       # False when re-ask template was used


# ── Slot confirmation (Step 3) ────────────────────────────────────────────────

class ConfirmationStatus(str, enum.Enum):
    CONFIRMED = "confirmed"   # user accepted — write to DB, go to Step 4
    PENDING   = "pending"     # user rejected or unclear — stay in Step 3
    PARTIAL   = "partial"     # user confirmed + changed one slot — re-present


class ConfirmationResponse(BaseModel):
    identity:             str
    message:              str
    confirmation_status:  ConfirmationStatus
    slots:                SlotState
    intention_id:         Optional[str] = None  # set only when confirmed


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

class GreetingResponse(BaseModel):
    message: str

class InspirationResponse(BaseModel):
    identity: str                   # resolved id (user_id or session_id)
    cache_hit: bool                 # was this served from Redis cache?
    data: InspirationPayload