import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.schemas.inspiration import (
    ConfirmationResponse,
    ConfirmationStatus,
    GreetingResponse,
    InspirationRequest,
    InspirationResponse,
    InspirationPayload,
    SlotChatResponse,
    SlotState,
)
from app.services import redis_service, llm_service
from app.services import extraction_service, confirmation_service
from app.services.llm_service import (
    GREETING_MESSAGE,
    get_reask_template,
    slots_complete,
    call_slot_llm,
    call_confirmation_llm,
    ConfirmationLLMResult,
    SlotLLMResult,
)

router = APIRouter(prefix="/ai", tags=["Inspiration"])


def _llm_error(detail: str) -> HTTPException:
    """502 for any upstream AI failure."""
    return HTTPException(status_code=502, detail=detail)


# ── Step 1 ─────────────────────────────────────────────────────────────────────

@router.get("/chat/greeting", response_model=GreetingResponse)
async def ai_greeting() -> GreetingResponse:
    """
    Return the static greeting message.

    No LLM call, no Redis read — pure static text served to every user.
    The message is designed to elicit destination, dates, group size,
    budget, and trip style in the user's first reply.
    """
    return GreetingResponse(message=GREETING_MESSAGE)


# ── Step 2 ─────────────────────────────────────────────────────────────────────

@router.post("/chat/collect", response_model=SlotChatResponse)
async def ai_collect(body: InspirationRequest) -> SlotChatResponse:
    """
    Slot collection endpoint.

    Decision tree per turn
    ----------------------
    1. Run spaCy extraction on the user message (~5 ms, no network).
    2. Merge newly found slots into the session's persisted slot state.
    3a. spaCy found nothing AND required slots still missing
          → return a pre-written re-ask template  (0 LLM calls)
    3b. spaCy found at least one slot OR all required slots already known
          → call LLM for response generation / implicit signal extraction
    4. Persist updated slots and conversation turn to Redis.
    5. Return SlotChatResponse (message + current slot state + completion flag).
    """

    # ── 1. Identity ──────────────────────────────────────────────────────────
    identity = body.user_id or body.session_id
    if not identity:
        raise HTTPException(
            status_code=400,
            detail="Either user_id or session_id must be provided.",
        )

    # ── 2. Load state from Redis ──────────────────────────────────────────────
    raw_slots, history = await _load_state(identity)

    # ── 3. spaCy extraction (Component 1) ────────────────────────────────────
    new_from_spacy = await extraction_service.extract_slots(
        text=body.message,
        existing_slots=raw_slots,
    )

    # Merge newly extracted slots into persisted state
    merged = {**raw_slots, **{k: v for k, v in new_from_spacy.items() if v}}
    merged.setdefault("mode", "slot_collection")

    complete = slots_complete(merged)

    # ── 4. Decide whether to call LLM (Component 2) ──────────────────────────
    used_llm = False

    if not new_from_spacy and not complete:
        # spaCy found nothing AND we still have missing required slots →
        # return a pre-written re-ask template — zero LLM calls.
        reply = get_reask_template(merged)

    else:
        # spaCy found something, or all required slots are already known →
        # ── LLM STUBBED FOR spaCy TESTING ────────────────────────────────────
        # try:
        #     result: SlotLLMResult = await call_slot_llm(
        #         user_message=body.message,
        #         conversation_history=history,
        #         current_slots=merged,
        #     )
        # except ValueError as exc:
        #     raise _llm_error(str(exc))
        # used_llm = True
        # reply = result.message
        # for k, v in result.new_slots.items():
        #     if v and not merged.get(k):
        #         merged[k] = v
        # ── END STUB ──────────────────────────────────────────────────────────
        used_llm = False
        reply = get_reask_template(merged)

        complete = slots_complete(merged)

    # ── 5. Advance session mode when collection is done ───────────────────────
    if complete:
        merged["mode"] = "confirmation"

    # ── 6. Persist slot state + conversation turn ─────────────────────────────
    await redis_service.save_slot_state(identity, merged)
    await redis_service.save_conversation_turn(
        identity=identity,
        user_message=body.message,
        assistant_payload=reply,
    )

    # ── 7. Build response ─────────────────────────────────────────────────────
    slot_state = SlotState(
        destination=merged.get("destination"),
        duration=merged.get("duration"),
        group_size=merged.get("group_size"),
        budget=merged.get("budget"),
        style=merged.get("style"),
        mode=merged.get("mode", "slot_collection"),
    )

    return SlotChatResponse(
        identity=identity,
        message=reply,
        slots=slot_state,
        slots_complete=complete,
        used_llm=used_llm,
    )


# ── Step 3 ─────────────────────────────────────────────────────────────────────

@router.post("/chat/confirm", response_model=ConfirmationResponse)
async def ai_confirm(body: InspirationRequest) -> ConfirmationResponse:
    """
    Step 3 — Slot confirmation endpoint.

    Three-layer detection per turn
    --------------------------------
    1. Call LLM → structured field confirmation_status (primary).
    2. Keyword override:
       - Reject signals ("but", "change", "actually") → force pending.
       - Confirm signals ("yes", "perfect") → force confirmed if LLM inconclusive.
    3. Ambiguity → pre-written explicit re-ask, capped at 1 attempt.

    Edge case — partial confirmation
    ---------------------------------
    "Yes but make it luxury" → update slot, re-present summary, stay in Step 3.

    On confirmed
    ------------
    - Write TripIntention to PostgreSQL.
    - Clear Redis slot state + conversation history.
    - Return intention_id → frontend transitions to Step 4.
    """

    # ── 1. Identity ──────────────────────────────────────────────────────────
    identity = body.user_id or body.session_id
    if not identity:
        raise HTTPException(
            status_code=400,
            detail="Either user_id or session_id must be provided.",
        )

    # ── 2. Load state ────────────────────────────────────────────────────────
    raw_slots, history = await _load_state(identity)

    if raw_slots.get("mode") != "confirmation":
        raise HTTPException(
            status_code=409,
            detail="Session is not in confirmation mode. Run /chat/collect first.",
        )

    # ── 3. LLM STUBBED FOR spaCy TESTING ─────────────────────────────────────
    # try:
    #     result: ConfirmationLLMResult = await call_confirmation_llm(
    #         user_message=body.message,
    #         conversation_history=history,
    #         current_slots=raw_slots,
    #     )
    # except ValueError as exc:
    #     raise _llm_error(str(exc))
    # ── END STUB ──────────────────────────────────────────────────────────────

    # ── 4. Three-layer confirmation detection (keyword layers only) ───────────
    # LLM layer stubbed — pass "ambiguous" so keyword Layer 2 drives the result.
    final_status = confirmation_service.detect_confirmation(
        user_text=body.message,
        llm_status="ambiguous",
    )

    # ── 5. No LLM slot updates while stubbed ─────────────────────────────────
    # if result.updated_slots:
    #     for k, v in result.updated_slots.items():
    #         if v:
    #             raw_slots[k] = v

    reply = confirmation_service.explicit_reask_message(raw_slots)
    intention_id: str | None = None

    # ── 6. Act on the final status ────────────────────────────────────────────
    if final_status == "confirmed":
        # Write to Postgres, wipe Redis, transition to Step 4
        intention_id = await confirmation_service.save_intention(
            session_id=body.session_id or identity,
            user_id=body.user_id,
            slots=raw_slots,
        )
        await redis_service.clear_session(identity)
        raw_slots["mode"] = "retrieval"

    elif final_status == "partial":
        # Slot updated above — stay in confirmation mode for one more turn
        raw_slots["mode"] = "confirmation"
        raw_slots.pop("confirmation_reask_count", None)   # reset ambiguity counter
        await redis_service.save_slot_state(identity, raw_slots)
        await redis_service.save_conversation_turn(
            identity=identity,
            user_message=body.message,
            assistant_payload=reply,
        )

    elif final_status == "ambiguous":
        # Layer 3: ask explicitly, but only once
        if confirmation_service.should_reask(raw_slots):
            raw_slots["confirmation_reask_count"] = (
                raw_slots.get("confirmation_reask_count", 0) + 1
            )
            reply = confirmation_service.explicit_reask_message(raw_slots)
        else:
            # Exhausted re-ask allowance → treat as pending
            final_status = "pending"
        await redis_service.save_slot_state(identity, raw_slots)
        await redis_service.save_conversation_turn(
            identity=identity,
            user_message=body.message,
            assistant_payload=reply,
        )

    else:
        # pending — stay in confirmation mode
        raw_slots["mode"] = "confirmation"
        await redis_service.save_slot_state(identity, raw_slots)
        await redis_service.save_conversation_turn(
            identity=identity,
            user_message=body.message,
            assistant_payload=reply,
        )

    # ── 7. Build response ─────────────────────────────────────────────────────
    slot_state = SlotState(
        destination=raw_slots.get("destination"),
        duration=raw_slots.get("duration"),
        group_size=raw_slots.get("group_size"),
        budget=raw_slots.get("budget"),
        style=raw_slots.get("style"),
        mode=raw_slots.get("mode", "confirmation"),
    )

    # Map "ambiguous" (internal) back to "pending" in the public response
    public_status = ConfirmationStatus(
        final_status if final_status in ("confirmed", "pending", "partial") else "pending"
    )

    return ConfirmationResponse(
        identity=identity,
        message=reply,
        confirmation_status=public_status,
        slots=slot_state,
        intention_id=intention_id,
    )


# ── Step 4 (existing inspiration endpoint — kept for backward compat) ──────────

def _extract_country(message: str) -> str:
    """
    Naive cache key — lowercased full message.
    Step 4 will replace this with proper destination slug from slot state.
    """
    return message.lower().strip()


@router.post("/chat", response_model=InspirationResponse)
async def ai_chat(body: InspirationRequest) -> InspirationResponse:
    """
    AI Inspiration chat endpoint (Step 4 — KB retrieval).

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

    # ── 3. Check global destination cache ─────────────────────────────────────
    cache_key = _extract_country(body.message)
    cached = await redis_service.get_cached_destination(cache_key)

    if cached:
        try:
            payload = InspirationPayload(**cached)
            cache_hit = True
        except ValidationError:
            cached = None

    if not cached:
        try:
            payload = await llm_service.call_llm(
                user_message=body.message,
                conversation_history=history,
            )

        except ValueError as e:
            raise _llm_error(str(e))

        except ValidationError as e:
            first = e.errors()[0]
            field = " → ".join(str(x) for x in first["loc"])
            raise _llm_error(
                f"LLM response missing or invalid field '{field}': {first['msg']}"
            )

        await redis_service.set_cached_destination(cache_key, payload.model_dump())
        cache_hit = False

    await redis_service.save_conversation_turn(
        identity=identity,
        user_message=body.message,
        assistant_payload=payload.model_dump(),
    )

    return InspirationResponse(
        identity=identity,
        cache_hit=cache_hit,
        data=payload,
    )


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _load_state(identity: str) -> tuple[dict, list[dict]]:
    """Load slot state and conversation history concurrently."""
    slots, history = await asyncio.gather(
        redis_service.load_slot_state(identity),
        redis_service.load_conversation(identity),
    )
    return slots, history
