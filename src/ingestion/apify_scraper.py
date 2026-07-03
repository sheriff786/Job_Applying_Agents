"""Apify integration for LinkedIn and Indeed job scraping.

Apify is a cloud web scraping platform with pre-built "actors" that can scrape
LinkedIn jobs, Indeed, Glassdoor, etc. - handling proxies, rate limiting, and
anti-bot measures automatically.

Why Apify?
- LinkedIn has NO public job API
- Direct scraping gets you banned instantly (IP blocks, CAPTCHAs)
- Apify handles browser automation, residential proxies, retries
- Pre-built actors are maintained by the community

Pricing: ~$49/month for 100 Actor runs (enough for daily job scraping)
Free tier: 30 runs/month (good for testing)

Setup:
1. Sign up at https://apify.com
2. Get your API token from Settings → Integrations
3. Add APIFY_API_TOKEN to your .env file
"""

import httpx
import asyncio
from datetime import datetime

from src.ingestion.base import BaseJobFetcher, RawJob
from src.config import settings


class ApifyLinkedInFetcher(BaseJobFetcher):
    """Fetches LinkedIn jobs using Apify's LinkedIn Jobs Scraper actor.
    
    Actor: https://apify.com/bebity/linkedin-jobs-scraper
    This actor scrapes LinkedIn job listings including:
    - Job title, company, location
    - Full job description
    - Posted date, applicant count
    - Remote/hybrid/onsite info
    """

    BASE_URL = "https://api.apify.com/v2"
    # Popular LinkedIn Jobs Scraper actor
    ACTOR_ID = "bebity/linkedin-jobs-scraper"

    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or getattr(settings, "apify_api_token", "")
        self.client = httpx.AsyncClient(timeout=120.0)  # Apify runs can take time

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Run Apify LinkedIn scraper and fetch results."""
        if not self.api_token:
            return []

        # Configure the scraper input
        run_input = {
            "searchUrl": self._build_linkedin_search_url(query, location),
            "scrapeJobDetails": True,
            "maxItems": 100,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        # Start the actor run
        run_url = f"{self.BASE_URL}/acts/{self.ACTOR_ID}/runs"
        headers = {"Authorization": f"Bearer {self.api_token}"}

        response = await self.client.post(
            run_url,
            json=run_input,
            headers=headers,
        )

        if response.status_code != 201:
            return []

        run_data = response.json().get("data", {})
        run_id = run_data.get("id")

        if not run_id:
            return []

        # Wait for the run to complete (poll every 10 seconds)
        dataset_items = await self._wait_for_results(run_id, headers)

        # Parse results into RawJob objects
        jobs = []
        for item in dataset_items:
            job = self._parse_linkedin_item(item)
            if job:
                jobs.append(job)

        return jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """Not needed - full details fetched in bulk."""
        return None

    async def _wait_for_results(
        self, run_id: str, headers: dict, max_wait: int = 300
    ) -> list[dict]:
        """Poll Apify until the run completes and return dataset items."""
        run_url = f"{self.BASE_URL}/actor-runs/{run_id}"
        elapsed = 0

        while elapsed < max_wait:
            response = await self.client.get(run_url, headers=headers)
            if response.status_code != 200:
                return []

            run_data = response.json().get("data", {})
            status = run_data.get("status")

            if status == "SUCCEEDED":
                # Fetch dataset items
                dataset_id = run_data.get("defaultDatasetId")
                return await self._fetch_dataset(dataset_id, headers)
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                return []

            await asyncio.sleep(10)
            elapsed += 10

        return []

    async def _fetch_dataset(self, dataset_id: str, headers: dict) -> list[dict]:
        """Fetch all items from an Apify dataset."""
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        params = {"format": "json", "limit": 100}

        response = await self.client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            return []

        return response.json()

    def _parse_linkedin_item(self, item: dict) -> RawJob | None:
        """Parse a single LinkedIn job item from Apify output."""
        title = item.get("title") or item.get("jobTitle", "")
        if not title:
            return None

        company = item.get("companyName") or item.get("company", "Unknown")
        description = item.get("description") or item.get("jobDescription", "")
        location = item.get("location") or item.get("jobLocation", "")
        job_url = item.get("url") or item.get("jobUrl", "")

        # Detect remote
        work_type = item.get("workType", "").lower()
        is_remote = "remote" in work_type or "remote" in location.lower()

        # Posted date
        posted = item.get("postedAt") or item.get("listedAt", "")

        return RawJob(
            source="linkedin_apify",
            external_id=f"li_apify_{item.get('id', job_url[-20:])}",
            company=company,
            title=title,
            description=description,
            location=location,
            remote=is_remote,
            url=job_url,
            posted_at=posted,
            salary_min=item.get("salaryMin"),
            salary_max=item.get("salaryMax"),
            metadata={
                "applicants": item.get("applicantsCount"),
                "seniority": item.get("seniorityLevel"),
                "employment_type": item.get("employmentType"),
                "industries": item.get("industries", []),
            },
        )

    def _build_linkedin_search_url(self, query: str, location: str | None) -> str:
        """Build LinkedIn job search URL."""
        base = "https://www.linkedin.com/jobs/search/?"
        params = [f"keywords={query.replace(' ', '%20')}"]

        if location:
            params.append(f"location={location.replace(' ', '%20')}")

        # Filter for remote jobs
        params.append("f_WT=2")  # Remote filter

        # Filter for experience level (mid-senior)
        params.append("f_E=3%2C4")  # 3=Mid-Senior, 4=Director

        return base + "&".join(params)


class ApifyIndeedFetcher(BaseJobFetcher):
    """Fetches Indeed jobs using Apify's Indeed Scraper actor.
    
    Actor: https://apify.com/misceres/indeed-scraper
    """

    BASE_URL = "https://api.apify.com/v2"
    ACTOR_ID = "misceres/indeed-scraper"

    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or getattr(settings, "apify_api_token", "")
        self.client = httpx.AsyncClient(timeout=120.0)

    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Run Apify Indeed scraper."""
        if not self.api_token:
            return []

        run_input = {
            "queries": [query],
            "location": location or "United States",
            "maxItems": 50,
            "parseCompanyUrl": True,
        }

        headers = {"Authorization": f"Bearer {self.api_token}"}
        run_url = f"{self.BASE_URL}/acts/{self.ACTOR_ID}/runs"

        response = await self.client.post(run_url, json=run_input, headers=headers)
        if response.status_code != 201:
            return []

        run_data = response.json().get("data", {})
        run_id = run_data.get("id")
        if not run_id:
            return []

        # Reuse wait logic
        linkedin_fetcher = ApifyLinkedInFetcher(self.api_token)
        dataset_items = await linkedin_fetcher._wait_for_results(run_id, headers)

        jobs = []
        for item in dataset_items:
            title = item.get("title", "")
            if not title:
                continue

            jobs.append(
                RawJob(
                    source="indeed_apify",
                    external_id=f"indeed_{item.get('id', title[:20])}",
                    company=item.get("company", "Unknown"),
                    title=title,
                    description=item.get("description", ""),
                    location=item.get("location", ""),
                    remote="remote" in item.get("location", "").lower(),
                    url=item.get("url", ""),
                    posted_at=item.get("date"),
                    salary_min=item.get("salaryMin"),
                    salary_max=item.get("salaryMax"),
                )
            )

        return jobs

    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        return None
