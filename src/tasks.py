"""Celery tasks for scheduled job fetching."""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

celery_app = Celery("job_agent", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.beat_schedule = {
    # Fetch new jobs every 6 hours
    "ingest-jobs": {
        "task": "src.tasks.ingest_jobs",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": ("software engineer",),
    },
    # Check email for updates every 2 hours
    "check-emails": {
        "task": "src.tasks.check_email_updates",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    # Parse and score new jobs every hour
    "process-pipeline": {
        "task": "src.tasks.process_new_jobs",
        "schedule": crontab(minute=30, hour="*/1"),
    },
}


@celery_app.task(name="src.tasks.ingest_jobs")
def ingest_jobs(query: str, location: str | None = None):
    """Scheduled task to ingest new jobs."""
    import asyncio
    from src.ingestion.orchestrator import IngestionOrchestrator
    from src.database import init_db

    async def _run():
        await init_db()
        orchestrator = IngestionOrchestrator()
        return await orchestrator.ingest_all(query, location)

    return asyncio.run(_run())


@celery_app.task(name="src.tasks.check_email_updates")
def check_email_updates():
    """Scheduled task to check Gmail for status updates."""
    import asyncio
    from src.mcp.gmail_mcp import GmailMCP
    from src.mcp.calendar_mcp import CalendarMCP

    async def _run():
        gmail = GmailMCP()
        calendar = CalendarMCP()
        updates = await gmail.check_for_updates()

        for update in updates:
            if update["detected_status"] == "interview":
                await calendar.create_interview_hold(
                    company=update["company"],
                    role="",
                )
        return updates

    return asyncio.run(_run())


@celery_app.task(name="src.tasks.process_new_jobs")
def process_new_jobs():
    """Parse and score newly ingested jobs."""
    import asyncio
    from src.pipeline import JobAgentPipeline

    async def _run():
        pipeline = JobAgentPipeline(user_profile_path="./data/user_profile.txt")
        await pipeline._parse_new_jobs()
        await pipeline._score_jobs()

    return asyncio.run(_run())
