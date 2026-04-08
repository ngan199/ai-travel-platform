"""
LLM service tests — prompt building + JSON parsing
File: backend/tests/test_llm_service.py

Strategy:
  We mock anthropic.AsyncAnthropic so no real HTTP calls are made.
  We verify:
    - valid JSON → parsed InspirationPayload
    - non-JSON → ValueError raised
    - missing required field → ValidationError raised
    - conversation history is forwarded in the messages list
    - system prompt is always sent
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.services.llm_service import call_llm, SYSTEM_PROMPT


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_client(text: str):
    """
    Builds a mock AsyncAnthropic client whose messages.create()
    returns a response with content[0].text = text.
    """
    mock_content = MagicMock()
    mock_content.text = text

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_create = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.messages.create = mock_create

    return mock_client


def patch_anthropic(text: str):
    """Patches anthropic.AsyncAnthropic in llm_service to return a fake client."""
    mock_client = make_mock_client(text)
    return patch(
        "app.services.llm_service.anthropic.AsyncAnthropic",
        return_value=mock_client,
    ), mock_client


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestValidResponse:

    @pytest.mark.asyncio
    async def test_valid_json_returns_inspiration_payload(self, valid_payload_dict):
        """
        A well-formed JSON response from the LLM must be parsed into
        an InspirationPayload with all fields intact.
        """
        patcher, _ = patch_anthropic(json.dumps(valid_payload_dict))
        with patcher:
            result = await call_llm(
                user_message="I want to visit Vietnam",
                conversation_history=[],
            )

        assert result.overview == valid_payload_dict["overview"]
        assert len(result.destinations) == len(valid_payload_dict["destinations"])
        assert result.suggested_days == valid_payload_dict["suggested_days"]
        assert len(result.follow_up_questions) == 3

    @pytest.mark.asyncio
    async def test_destination_cards_are_parsed(self, valid_payload_dict):
        """Each destination in the list must be a DestinationCard with all fields."""
        patcher, _ = patch_anthropic(json.dumps(valid_payload_dict))
        with patcher:
            result = await call_llm("beaches", [])

        dest = result.destinations[0]
        assert dest.name    == "Hội An"
        assert dest.country == "Vietnam"
        assert isinstance(dest.best_for, list)


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_non_json_response_raises_value_error(self):
        """
        If the LLM returns prose instead of JSON (prompt injection, hallucination),
        call_llm must raise ValueError — not crash with an unhandled exception.
        """
        patcher, _ = patch_anthropic("Sure! Here are some great destinations for you...")
        with patcher:
            with pytest.raises(ValueError, match="non-JSON"):
                await call_llm("I want beaches", [])

    @pytest.mark.asyncio
    async def test_missing_required_field_raises_validation_error(self, valid_payload_dict):
        """
        JSON that parses but is missing a required field (e.g. 'overview')
        must raise Pydantic's ValidationError.
        """
        broken = {k: v for k, v in valid_payload_dict.items() if k != "overview"}
        patcher, _ = patch_anthropic(json.dumps(broken))
        with patcher:
            with pytest.raises(ValidationError):
                await call_llm("vietnam trip", [])

    @pytest.mark.asyncio
    async def test_empty_string_response_raises_value_error(self):
        """An empty response body must raise ValueError."""
        patcher, _ = patch_anthropic("")
        with patcher:
            with pytest.raises(ValueError):
                await call_llm("south america", [])


class TestMessageBuilding:

    @pytest.mark.asyncio
    async def test_conversation_history_is_included(self, valid_payload_dict):
        """
        Previous turns from Redis must appear in the messages list sent to the LLM,
        before the new user message.
        """
        patcher, mock_client = patch_anthropic(json.dumps(valid_payload_dict))
        history = [
            {"role": "user",      "content": "Where should I go in Asia?"},
            {"role": "assistant", "content": {"overview": "Asia is vast..."}},
        ]

        with patcher:
            await call_llm("Tell me more about Vietnam", history)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Where should I go in Asia?"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Tell me more about Vietnam"

    @pytest.mark.asyncio
    async def test_system_prompt_is_always_sent(self, valid_payload_dict):
        """
        The system prompt must be included in every LLM request.
        This is what enforces the JSON-only output contract.
        """
        patcher, mock_client = patch_anthropic(json.dumps(valid_payload_dict))
        with patcher:
            await call_llm("I want to travel", [])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" in call_kwargs
        assert "JSON" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_new_user_message_is_last_in_list(self, valid_payload_dict):
        """The current user message must always be the final item in messages."""
        patcher, mock_client = patch_anthropic(json.dumps(valid_payload_dict))
        with patcher:
            await call_llm("final question", [
                {"role": "user",      "content": "earlier question"},
                {"role": "assistant", "content": "earlier answer"},
            ])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[-1]["content"] == "final question"
