"""
Shared fixtures for Steps 1-3 tests.

Strategy
--------
- LLM calls are commented out in inspiration.py — no LLM mocks needed.
- Redis is replaced with an in-memory dict so tests are fully self-contained.
- spaCy is loaded once for the entire session (200 ms startup cost, not per-test).
- DB writes (save_intention) are patched per-test in the files that need them.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services import extraction_service

# ── spaCy: load once for the whole session ────────────────────────────────────
extraction_service.init_nlp()


# ── In-memory Redis state ─────────────────────────────────────────────────────

@pytest.fixture
def redis_state() -> dict:
    """
    Fresh in-memory store for each test.
    Shape: {"slots": {}, "history": []}
    Tests can pre-seed slots or history before making requests.
    """
    return {"slots": {}, "history": []}


def _make_redis_patches(state: dict) -> dict[str, object]:
    """
    Return a {patch_target: async_replacement} mapping wired to `state`.
    All Redis service functions are replaced — no real Redis connection is made.
    """

    async def load_slot_state(identity: str) -> dict:
        return dict(state["slots"])

    async def save_slot_state(identity: str, slots: dict) -> None:
        state["slots"] = dict(slots)

    async def load_conversation(identity: str) -> list:
        return list(state["history"])

    async def save_conversation_turn(
        identity: str, user_message: str, assistant_payload
    ) -> None:
        state["history"].append({"role": "user", "content": user_message})
        state["history"].append({"role": "assistant", "content": assistant_payload})

    async def clear_session(identity: str) -> None:
        state["slots"].clear()
        state["history"].clear()

    return {
        "app.services.redis_service.load_slot_state": load_slot_state,
        "app.services.redis_service.save_slot_state": save_slot_state,
        "app.services.redis_service.load_conversation": load_conversation,
        "app.services.redis_service.save_conversation_turn": save_conversation_turn,
        "app.services.redis_service.clear_session": clear_session,
    }


# ── TestClient fixture ────────────────────────────────────────────────────────

@pytest.fixture
def client(redis_state):
    """
    FastAPI TestClient with:
    - Redis functions replaced by in-memory state
    - DB auto-create disabled
    - Scheduler patched out (no background jobs during tests)
    - Destination alias map set to empty (spaCy still uses its built-in NER)
    """
    from app.main import app

    redis_patches = _make_redis_patches(redis_state)

    with ExitStack() as stack:
        # Infrastructure patches
        stack.enter_context(patch("app.main.init_db"))
        stack.enter_context(patch("app.main.init_scheduler"))
        stack.enter_context(patch("app.main.scheduler", MagicMock()))
        stack.enter_context(patch("app.main._load_alias_map_sync", return_value={}))

        # Redis patches
        for target, fn in redis_patches.items():
            stack.enter_context(patch(target, new=fn))

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Reusable slot fixtures ────────────────────────────────────────────────────

@pytest.fixture
def full_slots() -> dict:
    """All 4 required slots + style filled, mode=confirmation."""
    return {
        "destination": "Thailand",
        "duration": "10 days",
        "group_size": "couple",
        "budget": "mid-range",
        "style": "beach",
        "mode": "confirmation",
    }


@pytest.fixture
def partial_slots() -> dict:
    """Only destination filled, mode=slot_collection."""
    return {
        "destination": "Japan",
        "mode": "slot_collection",
    }
