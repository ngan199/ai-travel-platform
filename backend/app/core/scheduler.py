import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_kb_refresh() -> None:
    """Async wrapper that runs the synchronous build_kb in a thread pool."""
    from scripts.build_kb import build_kb

    logger.info("Starting scheduled KB refresh ...")
    try:
        await asyncio.to_thread(build_kb)
        logger.info("Scheduled KB refresh complete.")
    except Exception:
        logger.exception("KB refresh failed")


def init_scheduler() -> None:
    scheduler.add_job(
        run_kb_refresh,
        trigger=CronTrigger(day=1, hour=2, minute=0),  # 1st of each month, 2 am
        id="kb_monthly_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — KB refresh runs on the 1st of each month at 02:00.")
