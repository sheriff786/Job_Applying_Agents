"""Wellfound (AngelList) job fetcher."""

import httpx
from bs4 import BeautifulSoup

from src.ingestion.base import BaseJobFetcher, RawJob


class WellfoundFetcher(BaseJobFetcher):
    """Fetches jobs from Wellfound (formerly AngelList Talent)."""

    BASE_URL = "https://wellfound.com"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Fetch jobs from Wellfound search."""
        # Wellfound requires scraping as they don't have a public API
        search_url = f"{self.BASE_URL}/role/{query.lower().replace(' ', '-')}"
        if location:
            search_url += f"/location/{location.lower().replace(' ', '-')}"

        response = await self.client.get(search_url)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []

        # Parse job listings from the page
        job_cards = soup.select("[data-test='StartupResult']")
        for card in job_cards:
            company_el = card.select_one("[data-test='startup-name']")
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            job_links = card.select("a[href*='/jobs/']")
            for link in job_links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                job_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                jobs.append(
                    RawJob(
                        source="wellfound",
                        external_id=f"wf_{href.split('/')[-1] if href else company}_{title[:20]}",
                        company=company,
                        title=title,
                        description="",  # Need to fetch detail page
                        location=location or "",
                        remote=False,
                        url=job_url,
                    )
                )

        return jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """Fetch detailed job info from Wellfound job page."""
        # Would need the full URL stored somewhere
        return None
