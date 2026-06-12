import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import AUTO_CREATE_TABLES
from app.core.scheduler import init_scheduler, scheduler
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.api.inspiration import router as inspiration_router
from app.db.redis_client import close_redis_client
from app.db.neo4j_client import get_neo4j_driver, close_neo4j_driver
from app.services import extraction_service

logger = logging.getLogger(__name__)


def _load_alias_map_sync() -> dict[str, str]:
    """
    Build a lowercase surface-form → canonical-name lookup from the
    Destination table.  Called once at startup in a thread pool so we
    don't block the event loop.
    """
    from app.models.destination import Destination

    alias_map: dict[str, str] = {}
    try:
        with SessionLocal() as db:
            rows = db.query(Destination.name, Destination.aliases).all()
        for name, aliases in rows:
            if name:
                alias_map[name.lower()] = name
            for alias in (aliases or []):
                if alias:
                    alias_map[alias.lower()] = name
    except Exception:
        # DB may not be populated yet during early dev — extraction still works
        # without aliases; destinations will just use the raw spaCy surface form.
        logger.warning("Could not load destination aliases from DB — skipping.")
    return alias_map


@asynccontextmanager
async def lifespan(_: FastAPI):
    if AUTO_CREATE_TABLES:
        init_db()
    init_scheduler()

    # ── spaCy pipeline + KB alias map (loaded once, reused for all requests) ──
    loop = asyncio.get_event_loop()
    # Run both blocking operations in the thread pool concurrently
    extraction_service.init_nlp()                              # spaCy load (~200 ms)
    alias_map = await loop.run_in_executor(None, _load_alias_map_sync)
    extraction_service.set_alias_map(alias_map)
    logger.info("spaCy pipeline ready. Loaded %d destination aliases.", len(alias_map))

    # ── Neo4j driver (verify connectivity at startup) ─────────────────────────
    try:
        get_neo4j_driver()
    except Exception as exc:
        logger.warning("Neo4j not available at startup: %s", exc)

    yield

    # ── shutdown ──────────────────────────────────────────────────────────────
    await close_redis_client()
    close_neo4j_driver()
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

# Add this line after your other app.include_router() calls:
app.include_router(inspiration_router)
