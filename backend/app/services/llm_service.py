import json
import anthropic
from app.core.config import settings
from app.schemas.inspiration import InspirationPayload

# ── System prompt ─────────────────────────────────────────────────────────────
# Strict JSON-only instruction so the LLM never wraps output in prose.

SYSTEM_PROMPT = """
You are Travester's AI travel inspiration assistant.
Your job is to inspire users to explore new destinations.

CRITICAL: You must respond ONLY with a valid JSON object — no markdown, no preamble, no explanation.
The JSON must exactly match this schema:

{
  "overview": "<2-3 sentence introduction about the destination or travel theme>",
  "destinations": [
    {
      "name": "<city or region name>",
      "country": "<country name>",
      "highlight": "<one compelling sentence about why to visit>",
      "best_for": ["<audience tag>", ...]
    }
  ],
  "best_time_to_visit": "<month range and reason>",
  "budget_usd_per_day": {
    "budget": <integer>,
    "mid": <integer>,
    "luxury": <integer>
  },
  "suggested_days": <integer>,
  "follow_up_questions": [
    "<question 1>",
    "<question 2>",
    "<question 3>"
  ]
}

Rules:
- Always include 3–5 destinations.
- follow_up_questions must be natural, conversational questions the user might ask next.
- budget_usd_per_day values are daily estimates per person excluding flights.
- Respond ONLY with the JSON. No other text.
"""


def _build_messages(history: list[dict], user_message: str) -> list[dict]:
    """
    Combine stored conversation history with the new user message.
    History items are already {"role": ..., "content": ...} dicts.
    The LLM sees the full conversation context, enabling follow-up awareness.
    """
    messages = []

    for item in history:
        role = item["role"]
        content = item["content"]
        # assistant turns were stored as dicts (the JSON payload); re-encode to string
        if role == "assistant" and isinstance(content, dict):
            content = json.dumps(content)
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages


async def call_llm(
    user_message: str,
    conversation_history: list[dict],
) -> InspirationPayload:
    """
    Call the Anthropic Claude API and parse the structured JSON response.
    Raises ValueError if the LLM returns malformed JSON.
    """
    if not settings.LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not configured.")

    messages = _build_messages(conversation_history, user_message)

    client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)

    response = await client.messages.create(
        model=settings.LLM_MODEL,
        system=SYSTEM_PROMPT,
        messages=messages,
        max_tokens=1500,
    )

    # Extract text content — adapt this selector to your LLM provider's response shape
    raw_text: str = response.content[0].text.strip()

    try:
        payload_dict = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned non-JSON content: {e}\nRaw: {raw_text[:300]}")

    return InspirationPayload(**payload_dict)
