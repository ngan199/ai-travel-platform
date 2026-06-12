"""
Unit tests for confirmation_service — pure logic, no HTTP, no DB, no Redis.

Covers the three-layer detection function and the re-ask helpers.
"""

import pytest
from app.services.confirmation_service import (
    detect_confirmation,
    explicit_reask_message,
    should_reask,
)


# ── detect_confirmation ───────────────────────────────────────────────────────

class TestRejectLayer:
    """Layer 2a — reject keywords override everything including LLM output."""

    @pytest.mark.parametrize("text", [
        "yes but change the budget",
        "actually let's do Japan",
        "wait, I want to change something",
        "nope that's wrong",
        "hmm not right",
        "I'm not sure about this",
        "maybe not",
    ])
    def test_reject_keyword_forces_pending(self, text):
        # Even if LLM says "confirmed", reject keyword wins
        assert detect_confirmation(text, llm_status="confirmed") == "pending"

    def test_but_overrides_llm_confirmed(self):
        assert detect_confirmation("yes but make it luxury", "confirmed") == "pending"

    def test_change_overrides_llm_partial(self):
        assert detect_confirmation("change the destination", "partial") == "pending"


class TestLLMLayer:
    """Layer 1 — LLM structured output used when no reject keyword found."""

    @pytest.mark.parametrize("status", ["confirmed", "pending", "partial"])
    def test_llm_status_trusted_without_keywords(self, status):
        assert detect_confirmation("I am thinking about it", status) == status

    def test_llm_confirmed_no_keywords(self):
        assert detect_confirmation("that works for me", "confirmed") == "confirmed"

    def test_llm_partial_no_keywords(self):
        assert detect_confirmation("that works for me", "partial") == "partial"

    def test_llm_pending_no_keywords(self):
        assert detect_confirmation("that works for me", "pending") == "pending"


class TestConfirmFallback:
    """Layer 2b — confirm keywords fire when LLM is inconclusive (ambiguous)."""

    @pytest.mark.parametrize("text", [
        "yes",
        "yeah",
        "yep",
        "yup",
        "correct",
        "perfect",
        "sure",
        "great",
        "go ahead",
        "let's go",
        "sounds good",
        "looks good",
        "ok",
        "okay",
        "absolutely",
        "confirmed",
    ])
    def test_confirm_keyword_when_llm_ambiguous(self, text):
        assert detect_confirmation(text, llm_status="ambiguous") == "confirmed"

    def test_confirm_keyword_does_not_override_llm_pending(self):
        # Layer 1 fires first (no reject keyword) → LLM pending is returned
        assert detect_confirmation("yes", llm_status="pending") == "pending"


class TestAmbiguousFallback:
    """Layer 3 — no signals from any layer → ambiguous."""

    def test_empty_message(self):
        assert detect_confirmation("blah blah blah", "ambiguous") == "ambiguous"

    def test_unrelated_text(self):
        assert detect_confirmation("I like pizza", "ambiguous") == "ambiguous"

    def test_question_without_signals(self):
        assert detect_confirmation("what does that mean?", "ambiguous") == "ambiguous"


class TestEdgeCases:
    def test_mixed_case_confirm(self):
        assert detect_confirmation("YES PLEASE", "ambiguous") == "confirmed"

    def test_punctuation_in_reject(self):
        assert detect_confirmation("no, actually I want Paris", "confirmed") == "pending"

    def test_confirm_keyword_in_longer_sentence(self):
        assert detect_confirmation("that sounds good to me", "ambiguous") == "confirmed"


# ── should_reask ──────────────────────────────────────────────────────────────

class TestShouldReask:
    def test_first_ambiguity_allows_reask(self):
        assert should_reask({"confirmation_reask_count": 0}) is True

    def test_reask_allowed_when_key_absent(self):
        assert should_reask({}) is True

    def test_second_ambiguity_blocks_reask(self):
        assert should_reask({"confirmation_reask_count": 1}) is False

    def test_high_count_blocks_reask(self):
        assert should_reask({"confirmation_reask_count": 5}) is False


# ── explicit_reask_message ────────────────────────────────────────────────────

class TestExplicitReaskMessage:
    def test_contains_destination(self):
        msg = explicit_reask_message({"destination": "Bali"})
        assert "Bali" in msg

    def test_contains_duration(self):
        msg = explicit_reask_message({"destination": "Bali", "duration": "10 days"})
        assert "10 days" in msg

    def test_contains_budget_label(self):
        msg = explicit_reask_message({"destination": "Bali", "budget": "luxury"})
        assert "luxury" in msg

    def test_fallback_when_no_slots(self):
        msg = explicit_reask_message({})
        assert len(msg) > 0

    def test_ends_with_action_prompt(self):
        msg = explicit_reask_message({"destination": "Japan"})
        # Message should invite the user to confirm or change
        lower = msg.lower()
        assert "yes" in lower or "change" in lower or "confirm" in lower
