"""
Unit tests for extraction_service — pure spaCy logic, no HTTP, no Redis.

Tests call _extract_sync() directly (the sync core) with an empty existing
dict so every extraction starts fresh.  spaCy is already loaded by conftest.
"""

import pytest
from app.services.extraction_service import _extract_sync

EMPTY = {}   # no existing slots


# ── Destination ───────────────────────────────────────────────────────────────

class TestDestination:
    def test_country_name(self):
        assert _extract_sync("I want to visit Japan", EMPTY)["destination"] == "Japan"

    def test_city_name(self):
        result = _extract_sync("trip to Paris next month", EMPTY)
        assert result.get("destination") == "Paris"

    def test_destination_not_extracted_when_no_gpe(self):
        result = _extract_sync("I love good food and adventure", EMPTY)
        assert "destination" not in result

    def test_existing_destination_not_overwritten(self):
        existing = {"destination": "Japan"}
        result = _extract_sync("France sounds good", existing)
        assert "destination" not in result   # should not add a new one


# ── Duration ──────────────────────────────────────────────────────────────────

class TestDuration:
    @pytest.mark.parametrize("text,expected", [
        ("trip for 10 days", "10 days"),
        # "2 week" (adj. form) — spaCy matches the singular "week" token
        ("a 2 week holiday", "2 week"),
        ("staying for 3 nights", "3 nights"),
        ("one month adventure", "one month"),
        ("seven days exploring", "seven days"),
        ("a week in the mountains", "a week"),
    ])
    def test_duration_patterns(self, text, expected):
        result = _extract_sync(text, EMPTY)
        assert result.get("duration") == expected

    def test_no_duration_without_time_reference(self):
        result = _extract_sync("I want to go to Thailand", EMPTY)
        assert "duration" not in result

    def test_existing_duration_not_overwritten(self):
        existing = {"duration": "7 days"}
        result = _extract_sync("a 2 week holiday", existing)
        assert "duration" not in result


# ── Group size ────────────────────────────────────────────────────────────────

class TestGroupSize:
    @pytest.mark.parametrize("text,expected", [
        ("traveling solo", "solo"),
        ("going alone", "alone"),
        ("just me on this trip", "just me"),
        ("by myself", "by myself"),
        ("couple trip with my partner", "couple"),
        ("my wife and I", "my wife"),
        ("family vacation with kids", "family"),
        ("bringing the children", "children"),
        ("group of 5 friends", "group of 5"),
        ("4 adults traveling together", "4 adults"),
    ])
    def test_group_patterns(self, text, expected):
        result = _extract_sync(text, EMPTY)
        assert result.get("group_size") == expected

    def test_existing_group_not_overwritten(self):
        existing = {"group_size": "solo"}
        result = _extract_sync("family trip", existing)
        assert "group_size" not in result


# ── Budget ────────────────────────────────────────────────────────────────────

class TestBudget:
    @pytest.mark.parametrize("text,expected", [
        ("luxury hotel experience", "luxury"),
        ("luxurious resort please", "luxury"),
        ("high-end accommodation", "luxury"),
        ("upscale dining", "luxury"),
        ("premium experience", "luxury"),
        ("tight budget trip", "budget"),
        ("budget travel", "budget"),
        ("cheap flights", "budget"),
        ("backpacker style", "budget"),
        ("affordable options", "budget"),
        ("economical choice", "budget"),
        ("mid-range hotel", "mid-range"),
        ("moderate spending", "mid-range"),
        ("midrange budget", "mid-range"),
        ("reasonable prices", "mid-range"),
    ])
    def test_budget_normalisation(self, text, expected):
        result = _extract_sync(text, EMPTY)
        assert result.get("budget") == expected

    def test_existing_budget_not_overwritten(self):
        existing = {"budget": "luxury"}
        result = _extract_sync("budget travel please", existing)
        assert "budget" not in result


# ── Style ─────────────────────────────────────────────────────────────────────

class TestStyle:
    @pytest.mark.parametrize("text,expected", [
        ("beach holiday", "beach"),
        ("I love surfing", "beach"),
        ("diving trip", "beach"),
        ("snorkeling adventure", "beach"),
        ("cultural experience", "culture"),
        ("visiting museums", "culture"),
        ("historical sites tour", "culture"),
        # "temples" (plural) is in STYLE_MAP; "temple" (singular) is not
        ("visiting temples", "culture"),
        ("hiking trip", "adventure"),
        ("trekking in the mountains", "adventure"),
        ("adventure sports", "adventure"),
        ("foodie paradise", "food"),
        ("culinary tour", "food"),
        ("street food lover", "food"),
        ("wildlife safari", "nature"),
        ("rainforest exploration", "nature"),
        ("national park visit", "nature"),
        ("eco tourism trip", "nature"),
    ])
    def test_style_normalisation(self, text, expected):
        result = _extract_sync(text, EMPTY)
        assert result.get("style") == expected

    def test_existing_style_not_overwritten(self):
        existing = {"style": "beach"}
        result = _extract_sync("hiking trip", existing)
        assert "style" not in result


# ── Multi-slot extraction ─────────────────────────────────────────────────────

class TestMultiSlot:
    def test_destination_and_duration_together(self):
        result = _extract_sync("Thailand for 10 days", EMPTY)
        assert result.get("destination") == "Thailand"
        assert result.get("duration") == "10 days"

    def test_three_slots_in_one_message(self):
        result = _extract_sync(
            "I'd love to go to Thailand for 10 days, beach vibes", EMPTY
        )
        assert result.get("destination") == "Thailand"
        assert result.get("duration") == "10 days"
        assert result.get("style") == "beach"

    def test_four_slots_in_rich_message(self):
        result = _extract_sync(
            "solo trip to Japan for 2 weeks, luxury budget", EMPTY
        )
        assert result.get("destination") == "Japan"
        assert result.get("duration") == "2 weeks"
        assert result.get("group_size") == "solo"
        assert result.get("budget") == "luxury"

    def test_empty_message_returns_empty_dict(self):
        result = _extract_sync("   ", EMPTY)
        assert result == {}

    def test_fully_loaded_existing_slots_skips_all(self):
        existing = {
            "destination": "Japan",
            "duration": "7 days",
            "group_size": "solo",
            "budget": "mid-range",
            "style": "culture",
        }
        result = _extract_sync(
            "luxury beach trip to Thailand for 2 weeks with a couple", existing
        )
        # Nothing should be extracted — all slots already filled
        assert result == {}
