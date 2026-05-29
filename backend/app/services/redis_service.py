import json
from typing import Optional
from app.db.redis_client import get_redis_client   # your existing client

CONVERSATION_TTL = 60 * 60 * 24 * 7   # 7 days  — user context window
CACHE_TTL        = 60 * 60 * 24       # 1 day   — destination info freshness
MAX_HISTORY_MSGS = 20                  # keep last N messages per session
SLOT_TTL         = 60 * 60 * 24 * 7   # 7 days  — slot state lifetime


def _conversation_key(identity: str) -> str:
    return f"ai:conversation:{identity}"


def _slot_key(identity: str) -> str:
    return f"ai:slots:{identity}"


def _cache_key(country: str) -> str:
    # normalise to lowercase slug so "Vietnam" and "vietnam" hit the same key
    return f"cache:destination:{country.lower().replace(' ', '_')}"

# ── Global destination cache ──────────────────────────────────────────────────

async def get_cached_destination(country: str) -> Optional[dict]:
    """Return cached destination payload or None on miss."""
    r = await get_redis_client()
    raw = await r.get(_cache_key(country))
    if raw is None:
        return None
    print("country", country)
    print("raw", raw)
    return json.loads(raw)


async def set_cached_destination(country: str, payload: dict) -> None:
    """Cache destination payload with a 1-day TTL."""
    r = await get_redis_client()
    await r.set(
        _cache_key(country),
        json.dumps(payload),
        ex=CACHE_TTL,
    )

# ── Slot state (Step 2) ──────────────────────────────────────────────────────

async def load_slot_state(identity: str) -> dict:
    """Return the stored slot dict for this identity, or {} on first visit."""
    r = await get_redis_client()
    raw = await r.get(_slot_key(identity))
    if raw is None:
        return {}
    print("slot raw", raw)
    print("identity", identity)
    return json.loads(raw)


async def save_slot_state(identity: str, slots: dict) -> None:
    """Persist the slot dict and refresh the TTL."""
    r = await get_redis_client()
    await r.set(_slot_key(identity), json.dumps(slots), ex=SLOT_TTL)


async def clear_session(identity: str) -> None:
    """
    Delete both the slot state and conversation history for this identity.
    Called on confirmed intent before transitioning to Step 4.
    """
    r = await get_redis_client()
    pipe = r.pipeline()
    pipe.delete(_slot_key(identity))
    pipe.delete(_conversation_key(identity))
    await pipe.execute()


# ── Conversation history ──────────────────────────────────────────────────────

async def load_conversation(identity: str) -> list[dict]:
    """Return the stored message list for this identity, oldest first."""
    r = await get_redis_client()
    key = _conversation_key(identity)
    raw = await r.lrange(key, 0, -1)           # all items, left→right
    print("conversation raw", raw)
    return [json.loads(item) for item in raw]


async def save_conversation_turn(
    identity: str,
    user_message: str,
    assistant_payload: dict | str,
) -> None:
    """
    Append both sides of the turn to the Redis list, then trim to MAX_HISTORY_MSGS
    pairs and refresh the TTL.  Each item is a JSON-encoded dict:
        {"role": "user"|"assistant", "content": str|dict}
    assistant_payload may be a plain str (slot collection) or a dict (inspiration).
    """
    r = await get_redis_client()
    key = _conversation_key(identity)

    user_entry = json.dumps({"role": "user", "content": user_message})
    assistant_entry = json.dumps({"role": "assistant", "content": assistant_payload})

    pipe = r.pipeline()
    pipe.rpush(key, user_entry)
    pipe.rpush(key, assistant_entry)
    # keep only the last MAX_HISTORY_MSGS * 2 entries (each turn = 2 messages)
    pipe.ltrim(key, -(MAX_HISTORY_MSGS * 2), -1)
    pipe.expire(key, CONVERSATION_TTL)
    await pipe.execute()
