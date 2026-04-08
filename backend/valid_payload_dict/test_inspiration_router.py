import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.schemas.inspiration import InspirationPayload
 
 
# ── Helpers ───────────────────────────────────────────────────────────────────
 
def make_payload(valid_payload_dict) -> InspirationPayload:
    return InspirationPayload(**valid_payload_dict)
 
 
# ── Tests ─────────────────────────────────────────────────────────────────────
 
class TestIdentityResolution:
    """The router must resolve an identity or reject the request."""
 
    @pytest.mark.asyncio
    async def test_returns_200_with_user_id(self, client, valid_payload_dict):
        payload = make_payload(valid_payload_dict)
        with (
            patch("app.api.inspiration.redis_service.load_conversation",    new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination", new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.redis_service.set_cached_destination", new=AsyncMock()),
            patch("app.api.inspiration.redis_service.save_conversation_turn",  new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                 new=AsyncMock(return_value=payload)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "I want to visit Vietnam",
                "user_id": "user-abc-123",
            })
        assert resp.status_code == 200
        assert resp.json()["identity"] == "user-abc-123"
 
    @pytest.mark.asyncio
    async def test_returns_200_with_session_id_only(self, client, valid_payload_dict):
        """Anonymous user — no user_id, only session_id."""
        payload = make_payload(valid_payload_dict)
        with (
            patch("app.api.inspiration.redis_service.load_conversation",    new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination", new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.redis_service.set_cached_destination", new=AsyncMock()),
            patch("app.api.inspiration.redis_service.save_conversation_turn",  new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                 new=AsyncMock(return_value=payload)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "I want to visit Vietnam",
                "session_id": "sess-xyz-999",
            })
        assert resp.status_code == 200
        assert resp.json()["identity"] == "sess-xyz-999"
 
    @pytest.mark.asyncio
    async def test_returns_400_when_no_identity(self, client):
        """Both user_id and session_id missing → 400."""
        resp = await client.post("/ai/chat", json={"message": "I want to visit Vietnam"})
        assert resp.status_code == 400
        assert "user_id" in resp.json()["detail"] or "session_id" in resp.json()["detail"]
 
 
class TestCacheBranching:
    """The cache hit/miss flag must reflect what actually happened."""
 
    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, client, valid_payload_dict):
        """
        When Redis has a cached destination, llm_service.call_llm must NOT be called
        and cache_hit must be True.
        """
        mock_llm = AsyncMock()
        with (
            patch("app.api.inspiration.redis_service.load_conversation",      new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=valid_payload_dict)),
            patch("app.api.inspiration.redis_service.save_conversation_turn",   new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                  new=mock_llm),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "vietnam beaches",
                "user_id": "user-1",
            })
 
        assert resp.status_code == 200
        assert resp.json()["cache_hit"] is True
        mock_llm.assert_not_called()       # LLM must never be called on a cache hit
 
    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm_and_stores(self, client, valid_payload_dict):
        """
        When cache is empty, the LLM must be called and the result stored in cache.
        cache_hit must be False.
        """
        payload = make_payload(valid_payload_dict)
        mock_set_cache = AsyncMock()
 
        with (
            patch("app.api.inspiration.redis_service.load_conversation",      new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.redis_service.set_cached_destination",  new=mock_set_cache),
            patch("app.api.inspiration.redis_service.save_conversation_turn",   new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                  new=AsyncMock(return_value=payload)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "tell me about japan",
                "user_id": "user-2",
            })
 
        assert resp.status_code == 200
        assert resp.json()["cache_hit"] is False
        mock_set_cache.assert_called_once()  # result must be stored in cache
 
 
class TestResponseShape:
    """The response must conform exactly to InspirationResponse."""
 
    @pytest.mark.asyncio
    async def test_response_has_required_fields(self, client, valid_payload_dict):
        payload = make_payload(valid_payload_dict)
        with (
            patch("app.api.inspiration.redis_service.load_conversation",      new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.redis_service.set_cached_destination",  new=AsyncMock()),
            patch("app.api.inspiration.redis_service.save_conversation_turn",   new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                  new=AsyncMock(return_value=payload)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "I want to explore Southeast Asia",
                "user_id": "user-3",
            })
 
        body = resp.json()
        assert "identity"  in body
        assert "cache_hit" in body
        assert "data"       in body
        data = body["data"]
        for field in ["overview", "destinations", "best_time_to_visit",
                      "budget_usd_per_day", "suggested_days", "follow_up_questions"]:
            assert field in data, f"Missing field in data: {field}"
 
    @pytest.mark.asyncio
    async def test_destinations_is_list(self, client, valid_payload_dict):
        payload = make_payload(valid_payload_dict)
        with (
            patch("app.api.inspiration.redis_service.load_conversation",      new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.redis_service.set_cached_destination",  new=AsyncMock()),
            patch("app.api.inspiration.redis_service.save_conversation_turn",   new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                  new=AsyncMock(return_value=payload)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "beach destinations",
                "user_id": "user-4",
            })
        assert isinstance(resp.json()["data"]["destinations"], list)
 
 
class TestErrorHandling:
    """Bad LLM output must not crash the server."""
 
    @pytest.mark.asyncio
    async def test_llm_bad_json_returns_502(self, client):
        """If llm_service raises ValueError (bad JSON), the router returns 502."""
        with (
            patch("app.api.inspiration.redis_service.load_conversation",      new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.llm_service.call_llm",
                  new=AsyncMock(side_effect=ValueError("LLM returned non-JSON"))),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "anywhere in europe",
                "user_id": "user-5",
            })
        assert resp.status_code == 502
        assert "non-JSON" in resp.json()["detail"]
 
 
class TestErrorHandlingExtended:
    """Covers the three new error cases added in the router fix."""
 
    @pytest.mark.asyncio
    async def test_llm_validation_error_returns_502(self, client):
        """
        ValidationError (valid JSON, missing field) must return 502
        with a readable field name in the detail — not a 500 crash.
        """
        # Build a real ValidationError by passing a bad dict to the schema
        try:
            InspirationPayload(**{"overview": "x"})   # missing all other fields
        except Exception as exc:
            validation_exc = exc
 
        with (
            patch("app.api.inspiration.redis_service.load_conversation",       new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.llm_service.call_llm",
                  new=AsyncMock(side_effect=validation_exc)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "I want to go somewhere",
                "user_id": "user-10",
            })
 
        assert resp.status_code == 502
        # Detail must name the missing field, not be a raw traceback
        assert "field" in resp.json()["detail"].lower() or "missing" in resp.json()["detail"].lower()
 
    @pytest.mark.asyncio
    async def test_llm_http_status_error_returns_502(self, client):
        """
        When the LLM API returns 429 or 503, httpx raises HTTPStatusError.
        The router must catch it and return a clean 502.
        """
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        http_exc = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_response
        )
 
        with (
            patch("app.api.inspiration.redis_service.load_conversation",       new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.llm_service.call_llm",
                  new=AsyncMock(side_effect=http_exc)),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "beaches in Thailand",
                "user_id": "user-11",
            })
 
        assert resp.status_code == 502
        assert "429" in resp.json()["detail"]
 
    @pytest.mark.asyncio
    async def test_llm_timeout_returns_502(self, client):
        """
        When the LLM API times out, the router must return 502
        with a human-readable message — not a 500 traceback.
        """
        with (
            patch("app.api.inspiration.redis_service.load_conversation",       new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=None)),
            patch("app.api.inspiration.llm_service.call_llm",
                  new=AsyncMock(side_effect=httpx.TimeoutException("timed out"))),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "where should I travel",
                "user_id": "user-12",
            })
 
        assert resp.status_code == 502
        assert "timed out" in resp.json()["detail"].lower()
 
    @pytest.mark.asyncio
    async def test_stale_cache_falls_through_to_llm(self, client, valid_payload_dict):
        """
        If cached data fails ValidationError (schema changed after deploy),
        the router must silently discard it and call the LLM instead.
        cache_hit must be False in the response.
        """
        stale_cached = {"broken": "data", "missing_all_required_fields": True}
        fresh_payload = InspirationPayload(**valid_payload_dict)
        mock_llm = AsyncMock(return_value=fresh_payload)
 
        with (
            patch("app.api.inspiration.redis_service.load_conversation",       new=AsyncMock(return_value=[])),
            patch("app.api.inspiration.redis_service.get_cached_destination",  new=AsyncMock(return_value=stale_cached)),
            patch("app.api.inspiration.redis_service.set_cached_destination",  new=AsyncMock()),
            patch("app.api.inspiration.redis_service.save_conversation_turn",   new=AsyncMock()),
            patch("app.api.inspiration.llm_service.call_llm",                  new=mock_llm),
        ):
            resp = await client.post("/ai/chat", json={
                "message": "Japan in spring",
                "user_id": "user-13",
            })
 
        assert resp.status_code == 200
        assert resp.json()["cache_hit"] is False   # stale cache was discarded
        mock_llm.assert_called_once()              # LLM was called as fallback
 