"""Ingestion orchestrator - coordinates fetching, deduplication, and normalization."""

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Job, async_session
from src.ingestion.base import RawJob
from src.ingestion.greenhouse import GreenhouseFetcher
from src.ingestion.lever import LeverFetcher
from src.ingestion.remoteok import RemoteOKFetcher
from src.ingestion.wellfound import WellfoundFetcher
from src.ingestion.linkedin import LinkedInExportParser
from src.ingestion.apify_scraper import ApifyLinkedInFetcher, ApifyIndeedFetcher
from src.config import settings


class IngestionOrchestrator:
    """Orchestrates job fetching from all sources with dedup and normalization."""

    # MAANG/FAANG and top product companies Greenhouse board tokens
    GREENHOUSE_BOARDS = [
        "google", "meta", "netflix", "apple", "amazon",
        "stripe", "airbnb", "databricks", "snowflake", "figma",
        "notion", "vercel", "supabase", "linear", "planetscale",
        "coinbase", "robinhood", "plaid", "rippling", "ramp",
    ]

    LEVER_COMPANIES = [
        "netflix", "stripe", "figma", "notion", "vercel",
        "openai", "anthropic", "databricks", "anduril", "scale",
    ]

    def __init__(self):
        self.fetchers = {
            "greenhouse": GreenhouseFetcher(board_tokens=self.GREENHOUSE_BOARDS),
            "lever": LeverFetcher(company_slugs=self.LEVER_COMPANIES),
            "remoteok": RemoteOKFetcher(),
            "wellfound": WellfoundFetcher(),
            "linkedin": LinkedInExportParser(),
        }

        # Add Apify scrapers if API token is configured
        if settings.apify_api_token:
            self.fetchers["linkedin_apify"] = ApifyLinkedInFetcher()
            self.fetchers["indeed_apify"] = ApifyIndeedFetcher()

    async def ingest_all(self, query: str, location: str | None = None) -> dict:
        """Fetch from all sources, deduplicate, and store."""
        stats = {"fetched": 0, "new": 0, "duplicates": 0, "errors": []}

        all_raw_jobs: list[RawJob] = []

        for source_name, fetcher in self.fetchers.items():
            try:
                jobs = await fetcher.fetch_jobs(query, location)
                all_raw_jobs.extend(jobs)
                stats["fetched"] += len(jobs)
            except Exception as e:
                stats["errors"].append(f"{source_name}: {str(e)}")

        # Deduplicate and store
        async with async_session() as session:
            for raw_job in all_raw_jobs:
                is_new = await self._store_if_new(session, raw_job)
                if is_new:
                    stats["new"] += 1
                else:
                    stats["duplicates"] += 1

            await session.commit()

        return stats

    async def _store_if_new(self, session: AsyncSession, raw_job: RawJob) -> bool:
        """Store job if it doesn't already exist. Returns True if new."""
        # Check by external_id
        existing = await session.execute(
            select(Job).where(Job.external_id == raw_job.external_id)
        )
        if existing.scalar_one_or_none():
            return False

        # Check by content hash (catches same job from different sources)
        content_hash = self._content_hash(raw_job)
        existing_by_hash = await session.execute(
            select(Job).where(
                Job.company == raw_job.company,
                Job.title == raw_job.title,
            )
        )
        if existing_by_hash.scalar_one_or_none():
            return False

        # Filter out India-based jobs
        if raw_job.location and self._is_excluded_location(raw_job.location):
            return False

        # Create new job record
        job = Job(
            source=raw_job.source,
            external_id=raw_job.external_id,
            company=raw_job.company,
            title=raw_job.title,
            description_raw=raw_job.description,
            location=raw_job.location,
            remote=raw_job.remote,
            url=raw_job.url,
            posted_at=self._parse_date(raw_job.posted_at),
            salary_min=raw_job.salary_min,
            salary_max=raw_job.salary_max,
            currency=raw_job.currency,
            status="new",
        )

        session.add(job)
        return True

    def _content_hash(self, raw_job: RawJob) -> str:
        """Generate a hash for deduplication."""
        content = f"{raw_job.company}|{raw_job.title}|{raw_job.description[:200]}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _is_excluded_location(self, location: str) -> bool:
        """Check if location is in excluded list."""
        location_lower = location.lower()
        for excluded in settings.excluded_locations:
            if excluded.lower() in location_lower:
                return True
        return False

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Try to parse a date string."""
        if not date_str:
            return None
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                return datetime.strptime(date_str[:19], fmt)
            except (ValueError, TypeError):
                continue
        return None
