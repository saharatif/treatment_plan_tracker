from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.checkpoints import evaluate_all_open_plans

checkpoint_scheduler = AsyncIOScheduler()


async def run_checkpoint_job() -> None:
    async with AsyncSessionLocal() as session:
        await evaluate_all_open_plans(session)


def start_scheduler() -> None:
    if not settings.enable_checkpoint_scheduler or checkpoint_scheduler.running:
        return
    checkpoint_scheduler.add_job(
        run_checkpoint_job,
        "cron",
        hour=settings.checkpoint_cron_hour,
        minute=0,
        id="daily_checkpoint_evaluation",
        replace_existing=True,
    )
    checkpoint_scheduler.start()


def shutdown_scheduler() -> None:
    if checkpoint_scheduler.running:
        checkpoint_scheduler.shutdown(wait=False)
