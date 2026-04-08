from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import AUTO_CREATE_TABLES
from app.db.init_db import init_db
from app.api.inspiration import router as inspiration_router
from app.db.redis_client import close_redis_client

@asynccontextmanager
async def lifespan(_: FastAPI):
    if AUTO_CREATE_TABLES:
        init_db()
    yield
    # --shutdown
    await close_redis_client()


app = FastAPI(lifespan=lifespan)

# Add this line after your other app.include_router() calls:
app.include_router(inspiration_router)
