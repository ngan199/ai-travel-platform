"""
Redis service tests — cache + conversation history
File: backend/tests/test_redis_service.py

Strategy:
  We use fakeredis.aioredis to create an in-memory Redis client.
  We patch get_redis_client() to return this fake client so
  redis_service functions run against it without a real Redis server.
"""

import json
import pytest
import pytest_asyncio
import fakeredis.aioredis as fakeredis
from unittest.mock import patch, AsyncMock

from app.services import redis_service


# ── Fixture: in-memory fake Redis client ─────────────────────────────────────

@pytest_asyncio.fixture
async def fake_redis():
    """
    Creates a fresh fakeredis instance per test.
    Each test gets a clean slate — no shared state between tests.
    """
    client = await fakeredis.FakeRedis()
    yield client
    await client.flushall()   # clean up after each test
    await client.aclose()


@pytest_asyncio.fixture(autouse=True)
async def patch_redis_client(fake_redis):
    """
    Auto-patches get_redis_client() for every test in this file.
    'autouse=True' means you don't have to explicitly request this fixture.
    """
    with patch(
        "app.services.redis_service.get_redis_client",
        new=AsyncMock(return_value=fake_redis),
    ):
        yield


# ── Destination cache tests ───────────────────────────────────────────────────

class TestDestinationCache:

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self):
        """A key that was never set must return None."""
        result = await redis_service.get_cached_destination("nonexistent_country")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_then_get_returns_same_payload(self, valid_payload_dict):
        """What we store must be exactly what we get back."""
        await redis_service.set_cached_destination("vietnam", valid_payload_dict)
        result = await redis_service.get_cached_destination("vietnam")
        assert result == valid_payload_dict

    @pytest.mark.asyncio
    async def test_country_name_is_normalised(self, valid_payload_dict):
        """
        'Vietnam' and 'vietnam' must hit the same cache key.
        The service lowercases the country name.
        """
        await redis_service.set_cached_destination("Vietnam", valid_payload_dict)
        result = await redis_service.get_cached_destination("vietnam")
        assert result is not None

    @pytest.mark.asyncio
    async def test_different_countries_dont_collide(self, valid_payload_dict, fake_redis):
        """Two different countries must not share cache entries."""
        japan_payload = {**valid_payload_dict, "overview": "Japan overview"}
        vietnam_payload = {**valid_payload_dict, "overview": "Vietnam overview"}

        await redis_service.set_cached_destination("japan", japan_payload)
        await redis_service.set_cached_destination("vietnam", vietnam_payload)

        assert (await redis_service.get_cached_destination("japan"))["overview"]   == "Japan overview"
        assert (await redis_service.get_cached_destination("vietnam"))["overview"] == "Vietnam overview"


# ── Conversation history tests ────────────────────────────────────────────────

class TestConversationHistory:

    @pytest.mark.asyncio
    async def test_load_empty_returns_empty_list(self):
        """A fresh identity has no conversation history."""
        result = await redis_service.load_conversation("new-user-id")
        assert result == []

    @pytest.mark.asyncio
    async def test_save_then_load_returns_both_roles(self, valid_payload_dict):
        """
        A single save_conversation_turn must persist both the user message
        and the assistant response, in that order.
        """
        await redis_service.save_conversation_turn(
            identity="user-abc",
            user_message="I want to visit Vietnam",
            assistant_payload=valid_payload_dict,
        )
        history = await redis_service.load_conversation("user-abc")

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "I want to visit Vietnam"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == valid_payload_dict

    @pytest.mark.asyncio
    async def test_multiple_turns_accumulate_in_order(self, valid_payload_dict):
        """Three turns = 6 messages, ordered oldest first."""
        for i in range(3):
            await redis_service.save_conversation_turn(
                identity="user-multi",
                user_message=f"Message {i}",
                assistant_payload=valid_payload_dict,
            )
        history = await redis_service.load_conversation("user-multi")
        assert len(history) == 6
        assert history[0]["content"] == "Message 0"
        assert history[2]["content"] == "Message 1"
        assert history[4]["content"] == "Message 2"

    @pytest.mark.asyncio
    async def test_history_trimmed_to_max_limit(self, valid_payload_dict):
        """
        After MAX_HISTORY_MSGS turns, the oldest messages must be dropped.
        MAX_HISTORY_MSGS = 20 turns = 40 stored messages max.
        We write 25 turns and expect only the last 20 (40 messages) to remain.
        """
        for i in range(25):
            await redis_service.save_conversation_turn(
                identity="user-trim",
                user_message=f"Message {i}",
                assistant_payload=valid_payload_dict,
            )
        history = await redis_service.load_conversation("user-trim")

        max_messages = redis_service.MAX_HISTORY_MSGS * 2   # 40
        assert len(history) == max_messages

        # The oldest 5 turns (10 messages) should be gone
        # The first remaining user message should be turn 5 ("Message 5")
        assert history[0]["content"] == "Message 5"

    @pytest.mark.asyncio
    async def test_different_identities_dont_share_history(self, valid_payload_dict):
        """Each identity has an isolated conversation namespace."""
        await redis_service.save_conversation_turn("user-A", "Hello from A", valid_payload_dict)
        await redis_service.save_conversation_turn("user-B", "Hello from B", valid_payload_dict)

        history_a = await redis_service.load_conversation("user-A")
        history_b = await redis_service.load_conversation("user-B")

        assert history_a[0]["content"] == "Hello from A"
        assert history_b[0]["content"] == "Hello from B"
        assert len(history_a) == 2
        assert len(history_b) == 2