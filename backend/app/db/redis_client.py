import redis.asyncio as redis
from app.core.config import settings

_redis_client: redis.Redis | None = None

async def get_redis_client() -> redis.Redis:
    """
    Return the shared async Redis client, creating it on first call.
 
    Thread-safe for asyncio (single event loop). The client uses a
    connection pool internally — no need to open/close per request.
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,  # All responses will be str instead of bytes
            max_connections=20,  # adjust based on expected load and Redis config
        )
        
    return _redis_client

async def close_redis_client() -> None:
    """
    Gracefully close the connection pool.
    Call this from the FastAPT lifespan shutdown handler.
    """
    
    global _redis_client 
    
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None