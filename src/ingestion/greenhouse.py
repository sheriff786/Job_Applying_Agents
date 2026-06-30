"""Greenhouse ATS job fetcher."""

import httpx

from src.ingestion.base import BaseJobFetcher, RawJob
from src.config import settings


class GreenhouseFetcher(BaseJobFetcher):
    """Fetches jobs from Greenhouse board APIs."""

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, board_tokens: list[str] | None = None):
        self.board_tokens = board_tokens or []
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_jobs_from_board(self, board_token: str) -> list[RawJob]:
        """Fetch all jobs from a specific Greenhouse board."""
        url = f"{self.BASE_URL}/{board_token}/jobs"
        params = {"content": "true"}
        response = await self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        jobs = []

        for job_data in data.get("jobs", []):
            location_name = ""
            if job_data.get("location"):
                location_name = job_data["location"].get("name", "")

            jobs.append(
                RawJob(
                    source="greenhouse",
                    external_id=f"gh_{board_token}_{job_data['id']}",
                    company=board_token,
                    title=job_data.get("title", ""),
                    description=job_data.get("content", ""),
                    location=location_name,
                    remote="remote" in location_name.lower(),
                    url=job_data.get("absolute_url"),
                    posted_at=job_data.get("updated_at"),
                )
            )

        return jobs

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Fetch jobs from all configured boards."""
        all_jobs = []
        for token in self.board_tokens:
            jobs = await self.fetch_jobs_from_board(token)
            # Filter by query in title
            filtered = [
                j for j in jobs if query.lower() in j.title.lower()
            ]
            if location:
                filtered = [
                    j for j in filtered
                    if j.location and location.lower() in j.location.lower()
                ]
            all_jobs.extend(filtered)
        return all_jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """Fetch a single job by board and ID."""
        parts = job_id.split("_")
        if len(parts) < 3:
            return None
        board_token = parts[1]
        gh_id = parts[2]

        url = f"{self.BASE_URL}/{board_token}/jobs/{gh_id}"
        response = await self.client.get(url, params={"content": "true"})
        if response.status_code != 200:
            return None

        job_data = response.json()
        location_name = ""
        if job_data.get("location"):
            location_name = job_data["location"].get("name", "")

        return RawJob(
            source="greenhouse",
            external_id=job_id,
            company=board_token,
            title=job_data.get("title", ""),
            description=job_data.get("content", ""),
            location=location_name,
            remote="remote" in location_name.lower(),
            url=job_data.get("absolute_url"),
            posted_at=job_data.get("updated_at"),
        )
