"""Base interface for all job source fetchers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawJob:
    """Raw job data before normalization."""

    source: str
    external_id: str
    company: str
    title: str
    description: str
    location: str | None = None
    remote: bool = False
    url: str | None = None
    posted_at: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    metadata: dict | None = None


class BaseJobFetcher(ABC):
    """Abstract base class for job source fetchers."""

    @abstractmethod
    async def fetch_jobs(self, query: str, location: str | None = None) -> list[RawJob]:
        """Fetch jobs from the source."""
        ...

    @abstractmethod
    async def fetch_job_detail(self, job_id: str) -> RawJob | None:
        """Fetch detailed info for a single job."""
        ...
