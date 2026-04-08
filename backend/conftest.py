import pytest
import pytest_asyncio
import fakeredis.aioredis as fakeredis
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app
 
 
@pytest.fixture
def valid_payload_dict():
    return {
        "overview": "Vietnam is a stunning destination with rich culture.",
        "destinations": [
            {
                "name": "Hội An",
                "country": "Vietnam",
                "highlight": "Lantern-lit ancient town with world-class street food.",
                "best_for": ["couples", "foodies"],
            }
        ],
        "best_time_to_visit": "November – March (dry season)",
        "budget_usd_per_day": {"budget": 30, "mid": 80, "luxury": 200},
        "suggested_days": 10,
        "follow_up_questions": [
            "Would you prefer beach or city experiences?",
            "Are you travelling solo or with family?",
            "What is your budget range?",
        ],
    }
 
 
@pytest_asyncio.fixture
async def fake_redis():
    """
    In-memory Redis that matches production client settings.
    decode_responses=True is REQUIRED — must match redis_client.py.
    """
    client = fakeredis.FakeRedis(decode_responses=True)   # ← key change
    yield client
    await client.flushall()
    await client.aclose()
 
 
@pytest_asyncio.fixture(autouse=True)
async def patch_redis_client(fake_redis):
    with patch(
        "app.services.redis_service.get_redis_client",
        new=AsyncMock(return_value=fake_redis),
    ):
        yield
 
 
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
 