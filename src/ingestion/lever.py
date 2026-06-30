"""Lever ATS job fetcher."""

import httpx

from src.ingestion.base import BaseJobFetcher, RawJob


class LeverFetcher(BaseJobFetcher):
    """Fetches jobs from Lever postings API."""

    BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, company_slugs: list[str] | None = None):
        self.company_slugs = company_slugs or []
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_jobs_from_company(self, company_slug: str) -> list[RawJob]:
        """Fetch all jobs from a Lever company page."""
        url = f"{self.BASE_URL}/{company_slug}"
        params = {"mode": "json"}
        response = await self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        jobs = []

        for posting in data:
            categories = posting.get("categories", {})
            location = categories.get("location", "")
            commitment = categories.get("commitment", "")

            jobs.append(
                RawJob(
                    source="lever",
                    external_id=f"lever_{company_slug}_{posting['id']}",
                    company=company_slug,
                    title=posting.get("text", ""),
                    description=posting.get("descriptionPlain", "")
                    or posting.get("description", ""),
                    location=location,
                    remote="remote" in location.lower() or "remote" in commitment.lower(),
                    url=posting.get("hostedUrl"),
                    posted_at=None,
                    metadata={
                        "team": categories.get("team", ""),
                        "department": categories.get("department", ""),
                    },
                )
            )

        return jobs

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Fetch jobs from all configured Lever companies."""
        all_jobs = []
        for slug in self.company_slugs:
            jobs = await self.fetch_jobs_from_company(slug)
            filtered = [j for j in jobs if query.lower() in j.title.lower()]
            if location:
                filtered = [
                    j for j in filtered
                    if j.location and location.lower() in j.location.lower()
                ]
            all_jobs.extend(filtered)
        return all_jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """Fetch single job detail from Lever."""
        parts = job_id.split("_")
        if len(parts) < 3:
            return None
        company_slug = parts[1]
        posting_id = parts[2]

        url = f"{self.BASE_URL}/{company_slug}/{posting_id}"
        response = await self.client.get(url)
        if response.status_code != 200:
            return None

        posting = response.json()
        categories = posting.get("categories", {})
        location = categories.get("location", "")

        return RawJob(
            source="lever",
            external_id=job_id,
            company=company_slug,
            title=posting.get("text", ""),
            description=posting.get("descriptionPlain", "") or posting.get("description", ""),
            location=location,
            remote="remote" in location.lower(),
            url=posting.get("hostedUrl"),
        )
