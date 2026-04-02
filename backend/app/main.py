from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import AUTO_CREATE_TABLES
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    if AUTO_CREATE_TABLES:
        init_db()
    yield


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Travester AI Orchestrator"}


@app.get("/health")
async def health_check():
    health = {"status": "unhealthy", "details": {}}

    # App level check
    health["details"]["app"] = "ok"

    # DB check
    try:
        from app.db.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["details"]["db"] = "ok"
    except Exception as exc:
        health["details"]["db"] = f"error: {exc}"

    # Redis check
    try:
        from app.db.redis_client import redis_client

        redis_client.ping()
        health["details"]["redis"] = "ok"
    except Exception as exc:
        health["details"]["redis"] = f"error: {exc}"

    if all(value == "ok" for value in health["details"].values()):
        health["status"] = "healthy"

    return health
