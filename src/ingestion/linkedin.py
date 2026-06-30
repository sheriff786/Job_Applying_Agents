"""LinkedIn job export parser - manual export, no auto-apply."""

import json
from pathlib import Path

from src.ingestion.base import BaseJobFetcher, RawJob
from src.config import settings


class LinkedInExportParser(BaseJobFetcher):
    """Parses manually exported LinkedIn job data.

    LinkedIn prohibits automated scraping. This parser handles:
    1. JSON exports from browser extensions (e.g., LinkedIn Job Scraper)
    2. CSV exports from LinkedIn's "Applied Jobs" page
    3. Manual copy-paste job descriptions saved as text files
    """

    def __init__(self, export_dir: str | None = None):
        self.export_dir = Path(export_dir or settings.linkedin_export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Parse all exported LinkedIn jobs from the export directory."""
        jobs = []

        # Parse JSON exports
        for json_file in self.export_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        job = self._parse_json_job(item)
                        if job and query.lower() in job.title.lower():
                            jobs.append(job)
                elif isinstance(data, dict):
                    job = self._parse_json_job(data)
                    if job and query.lower() in job.title.lower():
                        jobs.append(job)
            except (json.JSONDecodeError, KeyError):
                continue

        # Filter by location if specified
        if location:
            jobs = [
                j for j in jobs if j.location and location.lower() in j.location.lower()
            ]

        return jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """Not applicable for exports."""
        return None

    def _parse_json_job(self, data: dict) -> RawJob | None:
        """Parse a single job from JSON export."""
        title = data.get("title") or data.get("jobTitle") or data.get("position", "")
        if not title:
            return None

        return RawJob(
            source="linkedin",
            external_id=f"li_{data.get('id', data.get('jobId', title[:30]))}",
            company=data.get("company") or data.get("companyName", "Unknown"),
            title=title,
            description=data.get("description") or data.get("jobDescription", ""),
            location=data.get("location") or data.get("jobLocation", ""),
            remote="remote" in (data.get("location", "") + data.get("title", "")).lower(),
            url=data.get("url") or data.get("jobUrl"),
            posted_at=data.get("postedAt") or data.get("date"),
        )
