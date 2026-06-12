import json

from openai import AsyncOpenAI, APIError

from app.core.config import settings
from app.schemas.inspiration import InspirationPayload

# ── Client singleton ──────────────────────────────────────────────────────────
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


# ── Greeting message (Step 1) ─────────────────────────────────────────────────

GREETING_MESSAGE = (
    "Hi! Tell me about your dream getaway — where in the world you want to go, "
    "when you're thinking of traveling, who's coming along, your rough budget, "
    "and the vibe you're after — and I'll craft the perfect inspiration for you."
)


# ── History builders ──────────────────────────────────────────────────────────

def _build_messages(history: list[dict], user_message: str) -> list[dict]:
    """
    Convert Redis conversation history to OpenAI messages format.
    Redis stores role as "user"/"assistant" — matches OpenAI directly.
    Assistant turns stored as dicts are re-serialised to JSON strings.
    """
    messages: list[dict] = []

    for item in history:
        content = item["content"]
        if isinstance(content, dict):
            content = json.dumps(content)
        messages.append({"role": item["role"], "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages


_REQUIRED_SLOTS = ["destination", "duration", "group_size", "budget"]
_SLOT_PRIORITY  = [*_REQUIRED_SLOTS, "style"]
_SLOT_FIELDS    = frozenset(_SLOT_PRIORITY)


def _build_slot_messages(
    history: list[dict],
    user_message: str,
    current_slots: dict,
) -> list[dict]:
    """
    Like _build_messages but appends a <slot_state> tag to the current user
    message so the model knows which slots are already filled.
    Only the 5 named slot fields are included — not internal keys like "mode"
    or "confirmation_reask_count".
    """
    messages: list[dict] = []

    for item in history:
        content = item["content"]
        if isinstance(content, dict):
            content = json.dumps(content)
        messages.append({"role": item["role"], "content": content})

    filled = {k: v for k, v in current_slots.items() if k in _SLOT_FIELDS and v}
    slot_tag = json.dumps(
        {"filled_slots": filled, "mode": current_slots.get("mode", "slot_collection")},
        separators=(",", ":"),
    )
    full_message = f"{user_message}\n<slot_state>{slot_tag}</slot_state>"
    messages.append({"role": "user", "content": full_message})
    return messages


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Inspiration
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Travesta's AI travel inspiration assistant.
Your job is to inspire users to explore new destinations.

Respond ONLY with a valid JSON object matching this schema exactly — no markdown, no preamble:
{
  "overview": "<2-3 sentence introduction about the destination or travel theme>",
  "destinations": [
    {
      "name": "<city or region name>",
      "country": "<country name>",
      "highlight": "<one compelling sentence about why to visit>",
      "best_for": ["<audience tag>"]
    }
  ],
  "best_time_to_visit": "<month range and reason>",
  "budget_usd_per_day": {
    "budget": <integer>,
    "mid": <integer>,
    "luxury": <integer>
  },
  "suggested_days": <integer>,
  "follow_up_questions": ["<question 1>", "<question 2>", "<question 3>"]
}

Rules:
- Always include 3-5 destinations.
- follow_up_questions must be natural, conversational questions the user might ask next.
- budget_usd_per_day values are daily estimates per person excluding flights.
"""


async def call_llm(
    user_message: str,
    conversation_history: list[dict],
) -> InspirationPayload:
    """
    Step 4 — Call OpenAI and parse the structured JSON response.
    Raises ValueError on bad JSON or API errors.
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured.")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _build_messages(conversation_history, user_message)

    try:
        response = await _get_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
    except APIError as exc:
        raise ValueError(f"OpenAI API error {exc.status_code}: {exc.message}")

    raw_text: str = (response.choices[0].message.content or "").strip()

    try:
        payload_dict = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI returned non-JSON: {exc}\nRaw: {raw_text[:300]}")

    return InspirationPayload(**payload_dict)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Slot Collection
# ─────────────────────────────────────────────────────────────────────────────

SLOT_SYSTEM_PROMPT = """\
You are Travesta's AI travel companion. Your job is to collect the user's trip
details through a friendly, natural conversation — not an interrogation.

## Slots to collect
| Slot        | Required | Valid values |
|-------------|----------|--------------|
| destination | yes      | any place name |
| duration    | yes      | free text, e.g. "7 days", "2 weeks" |
| group_size  | yes      | "solo", "couple", "family with children", "group of N" |
| budget      | yes      | "luxury" | "mid-range" | "budget" |
| style       | optional | "beach" | "culture" | "adventure" | "food" | "nature" |

## Input
Each request ends with a <slot_state> XML tag containing already-known values and
the current session mode. Do NOT re-ask for filled slots.

## Extraction rules
1. Extract implicit signals: "family trip" → group_size includes children;
   "good food" → style hint; "backpacking" → budget.
2. Normalise budget: luxury/high-end/upscale → "luxury";
   cheap/affordable/backpacker → "budget"; anything in between → "mid-range".
3. Normalise style: beach/diving/surfing → "beach"; temples/museum/history →
   "culture"; hiking/trekking → "adventure"; foodie/cuisine → "food";
   wildlife/safari/rainforest → "nature".

## Conversation rules
1. Ask at most 2 missing slots per reply — never enumerate all gaps at once.
2. Priority order: destination → duration → group_size → budget → style.
3. Acknowledge what the user shared before asking what's missing.
4. Keep replies short (1-3 sentences) during collection.
5. When all required slots are known, confirm with a brief summary and ask
   the user to verify: "So that's [destination], [duration], [group_size],
   [budget] budget — sound right?"

## Output format — ONLY valid JSON, no markdown, no preamble
{
  "slots": {
    "destination": "<string or null — only NEW value, null if unchanged>",
    "duration":    "<string or null>",
    "group_size":  "<string or null>",
    "budget":      "<luxury|mid-range|budget or null>",
    "style":       "<beach|culture|adventure|food|nature or null>"
  },
  "message": "<your conversational reply>"
}

## Few-shot examples

### Example A — first message, multiple signals
<slot_state>{"filled_slots":{},"mode":"slot_collection"}</slot_state>
User: "I'd love to go to Thailand for 10 days, beach vibes"
{"slots":{"destination":"Thailand","duration":"10 days","style":"beach"},\
"message":"Thailand is a great choice for beach time! Will you be going solo \
or with someone, and what's your rough budget level?"}

### Example B — implicit group signal
<slot_state>{"filled_slots":{"destination":"Japan","duration":"2 weeks"},\
"mode":"slot_collection"}</slot_state>
User: "family trip with two kids, we love good food"
{"slots":{"group_size":"family with children","style":"food"},\
"message":"A foodie family trip to Japan for 2 weeks — love it! Last thing: \
what kind of budget are you working with?"}

### Example C — ambiguous budget, inferred
<slot_state>{"filled_slots":{"destination":"Portugal","duration":"1 week",\
"group_size":"couple"},"mode":"slot_collection"}</slot_state>
User: "we're backpacking on a tight budget"
{"slots":{"budget":"budget"},\
"message":"Got it — Portugal, 1 week, just the two of you, budget travel. \
Sound right?"}

### Example D — all required slots present, confirmation prompt
<slot_state>{"filled_slots":{"destination":"Bali","duration":"10 days",\
"group_size":"couple","budget":"mid-range","style":"beach"},\
"mode":"slot_collection"}</slot_state>
User: "yeah that all sounds correct"
{"slots":{},"message":"Perfect — Bali, 10 days, couple, mid-range budget, \
beach focus. Let me find the best options for you!"}
"""

_REASK_TEMPLATES: dict[str, str] = {
    "destination": (
        "Where are you thinking of heading — "
        "anywhere specific in mind, or still exploring options?"
    ),
    "duration": "How long were you thinking of traveling for?",
    "group_size": "Just you, or will others be joining you?",
    "budget": (
        "Any rough sense of budget — "
        "going all out, keeping it moderate, or traveling lean?"
    ),
    "style": (
        "What kind of experience are you after — "
        "beach, culture, adventure, food, or something else?"
    ),
}


def get_reask_template(slots: dict) -> str:
    """Return the pre-written re-ask for the highest-priority missing slot."""
    for slot in _SLOT_PRIORITY:
        if not slots.get(slot):
            return _REASK_TEMPLATES[slot]
    return "Could you share a bit more about what you're looking for?"


def slots_complete(slots: dict) -> bool:
    """True when all 4 required slots have non-empty values."""
    return all(slots.get(s) for s in _REQUIRED_SLOTS)


class SlotLLMResult:
    __slots__ = ("message", "new_slots")

    def __init__(self, message: str, new_slots: dict) -> None:
        self.message = message
        self.new_slots = new_slots


async def call_slot_llm(
    user_message: str,
    conversation_history: list[dict],
    current_slots: dict,
) -> SlotLLMResult:
    """Step 2 — Call OpenAI for slot collection."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured.")

    messages = [{"role": "system", "content": SLOT_SYSTEM_PROMPT}]
    messages += _build_slot_messages(conversation_history, user_message, current_slots)

    try:
        response = await _get_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=512,
        )
    except APIError as exc:
        raise ValueError(f"OpenAI API error {exc.status_code}: {exc.message}")

    raw: str = (response.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Slot LLM returned non-JSON: {exc}\nRaw: {raw[:300]}")

    return SlotLLMResult(
        message=data.get("message", ""),
        new_slots=data.get("slots", {}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Slot Confirmation
# ─────────────────────────────────────────────────────────────────────────────

CONFIRMATION_SYSTEM_PROMPT = """\
You are Travesta's AI travel companion confirming a trip summary with the user.

## Your task
Interpret the user's reply and return one of three confirmation statuses:
- "confirmed"  The user accepted the summary as-is.
- "partial"    The user accepted but wants to change exactly one slot.
               Extract the change into updated_slots and re-present the summary.
- "pending"    The user rejected, is uncertain, or wants major changes.

## Input
Each request ends with a <slot_state> tag containing current trip details.

## Partial-update extraction
When the user says "yes but make it luxury" or "correct, but 2 weeks instead":
- Set confirmation_status to "partial"
- Put only the changed field in updated_slots (null for everything else)
- Compose message as a NEW summary of the fully updated trip ending with
  "Does that look right now?"

## Output format — ONLY valid JSON, no markdown, no preamble
{
  "confirmation_status": "confirmed | pending | partial",
  "updated_slots": {
    "destination": null,
    "duration":    null,
    "group_size":  null,
    "budget":      null,
    "style":       null
  },
  "message": "<your response to the user>"
}

## Few-shot examples

### A — user confirms cleanly
<slot_state>{"filled_slots":{"destination":"Thailand","duration":"10 days",\
"group_size":"couple","budget":"mid-range","style":"beach"},\
"mode":"confirmation"}</slot_state>
User: "Yes that sounds perfect!"
{"confirmation_status":"confirmed","updated_slots":{},\
"message":"Great — Thailand, 10 days, couple, mid-range budget, beach. Let me build your options!"}

### B — partial: slot change + confirm
<slot_state>{"filled_slots":{"destination":"Thailand","duration":"10 days",\
"group_size":"couple","budget":"mid-range","style":"beach"},\
"mode":"confirmation"}</slot_state>
User: "Yes but make the budget luxury"
{"confirmation_status":"partial","updated_slots":{"budget":"luxury"},\
"message":"Updated! So: Thailand, 10 days, couple, luxury budget, beach focus. Does that look right now?"}

### C — user rejects / wants major change
<slot_state>{"filled_slots":{"destination":"Thailand","duration":"10 days",\
"group_size":"couple","budget":"mid-range"},"mode":"confirmation"}</slot_state>
User: "Actually I changed my mind, let's do Japan"
{"confirmation_status":"pending","updated_slots":{"destination":"Japan"},\
"message":"No problem! I've updated the destination to Japan. Just to confirm: Japan, 10 days, couple, mid-range budget. Sound right?"}
"""


class ConfirmationLLMResult:
    __slots__ = ("message", "status", "updated_slots")

    def __init__(self, message: str, status: str, updated_slots: dict) -> None:
        self.message = message
        self.status = status
        self.updated_slots = updated_slots


async def call_confirmation_llm(
    user_message: str,
    conversation_history: list[dict],
    current_slots: dict,
) -> ConfirmationLLMResult:
    """Step 3 — Call OpenAI to interpret the user's confirmation response."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured.")

    messages = [{"role": "system", "content": CONFIRMATION_SYSTEM_PROMPT}]
    messages += _build_slot_messages(conversation_history, user_message, current_slots)

    try:
        response = await _get_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=400,
        )
    except APIError as exc:
        raise ValueError(f"OpenAI API error {exc.status_code}: {exc.message}")

    raw: str = (response.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Confirmation LLM returned non-JSON: {exc}\nRaw: {raw[:300]}")

    return ConfirmationLLMResult(
        message=data.get("message", ""),
        status=data.get("confirmation_status", "pending"),
        updated_slots=data.get("updated_slots", {}),
    )
