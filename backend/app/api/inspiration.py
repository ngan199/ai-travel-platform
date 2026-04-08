from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
import httpx

from app.schemas.inspiration import (
    InspirationRequest,
    InspirationResponse,
    InspirationPayload,
)
from app.services import redis_service, llm_service

router = APIRouter(prefix="/ai", tags=["Inspiration"])


def _extract_country(message: str) -> str:
    """
    Naive cache key — lowercased full message.
    Phase 2: replace with NER / keyword extraction.
    """
    return message.lower().strip()


def _llm_error(detail: str) -> HTTPException:
    """
    Single place that produces a 502 for any upstream AI failure.
    502 = "we got a bad response from a gateway we depend on" — correct
    semantics for LLM / cache data problems.
    """
    return HTTPException(status_code=502, detail=detail)


@router.post("/chat", response_model=InspirationResponse)
async def ai_chat(body: InspirationRequest) -> InspirationResponse:
    """
    AI Inspiration chat endpoint.

    Error contract:
      400 → caller mistake (missing identity)
      502 → upstream failure (LLM bad JSON, schema mismatch, API error)
      500 → genuine unexpected bug (we never raise this intentionally)
    """

    # ── 1. Identity resolution ────────────────────────────────────────────────
    identity = body.user_id or body.session_id
    if not identity:
        raise HTTPException(
            status_code=400,
            detail="Either user_id or session_id must be provided.",
        )

    # ── 2. Load conversation context ──────────────────────────────────────────
    history = await redis_service.load_conversation(identity)

    # ── 3. Intent detection (hardcoded for Phase 1) ───────────────────────────
    intent = "inspiration"  # noqa: F841  — Phase 2 will use this

    # ── 4. Check global destination cache ─────────────────────────────────────
    cache_key = _extract_country(body.message)
    cached = await redis_service.get_cached_destination(cache_key)

    if cached:
        # ── 5a. Cache HIT ─────────────────────────────────────────────────────
        # GAP 1 FIX: wrap in try/except ValidationError.
        # Cached data can be stale if the schema changed after a deploy.
        # Rather than crashing, we treat it as a cache miss and call the LLM.
        try:
            payload = InspirationPayload(**cached)
            cache_hit = True
        except ValidationError:
            # Stale cache — fall through to LLM call below
            cached = None

    if not cached:
        # ── 5b. Cache MISS: call LLM ──────────────────────────────────────────
        # GAP 2 FIX: catch ValidationError alongside ValueError.
        # GAP 3 FIX: catch httpx.HTTPStatusError for LLM API 4xx/5xx responses.
        try:
            payload = await llm_service.call_llm(
                user_message=body.message,
                conversation_history=history,
            )

        except ValueError as e:
            # LLM returned a response that wasn't valid JSON at all
            raise _llm_error(f"LLM returned unparseable response: {e}")

        except ValidationError as e:
            # LLM returned valid JSON but a field was missing or wrong type
            # e.errors() gives a clean list — we take the first one for the message
            first = e.errors()[0]
            field = " → ".join(str(x) for x in first["loc"])
            raise _llm_error(
                f"LLM response missing or invalid field '{field}': {first['msg']}"
            )

        except httpx.HTTPStatusError as e:
            # LLM API returned 429 rate limit, 503 unavailable, etc.
            raise _llm_error(
                f"LLM API error {e.response.status_code}: {e.response.text[:200]}"
            )

        except httpx.TimeoutException:
            # LLM API took longer than the 30s timeout in llm_service
            raise _llm_error("LLM API timed out — try again in a moment")

        # ── 5c. Store fresh result in global cache ────────────────────────────
        await redis_service.set_cached_destination(cache_key, payload.model_dump())
        cache_hit = False

    # ── 6. Save conversation turn ──────────────────────────────────────────────
    await redis_service.save_conversation_turn(
        identity=identity,
        user_message=body.message,
        assistant_payload=payload.model_dump(),
    )

    # ── 7. Return structured response ──────────────────────────────────────────
    return InspirationResponse(
        identity=identity,
        cache_hit=cache_hit,
        data=payload,
    )