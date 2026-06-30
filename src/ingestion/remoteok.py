"""RemoteOK job board fetcher."""

import httpx

from src.ingestion.base import BaseJobFetcher, RawJob


class RemoteOKFetcher(BaseJobFetcher):
    """Fetches remote jobs from RemoteOK API."""

    BASE_URL = "https://remoteok.com/api"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "JobApplyingAgent/1.0"},
        )

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Fetch remote jobs matching the query."""
        url = self.BASE_URL
        response = await self.client.get(url)
        response.raise_for_status()

        data = response.json()
        # First item is metadata, skip it
        postings = data[1:] if len(data) > 1 else []

        jobs = []
        for posting in postings:
            title = posting.get("position", "")
            company = posting.get("company", "")
            description = posting.get("description", "")

            # Filter by query
            if query.lower() not in title.lower() and query.lower() not in description.lower():
                continue

            tags = posting.get("tags", [])

            jobs.append(
                RawJob(
                    source="remoteok",
                    external_id=f"remoteok_{posting.get('id', '')}",
                    company=company,
                    title=title,
                    description=description,
                    location=posting.get("location", "Worldwide"),
                    remote=True,
                    url=posting.get("url", f"https://remoteok.com/l/{posting.get('slug', '')}"),
                    posted_at=posting.get("date"),
                    salary_min=posting.get("salary_min"),
                    salary_max=posting.get("salary_max"),
                    metadata={"tags": tags},
                )
            )

        return jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """RemoteOK doesn't have individual job API, return None."""
        return None
