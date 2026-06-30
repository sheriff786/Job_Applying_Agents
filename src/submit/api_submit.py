"""API Auto-submit - Submits applications via ATS APIs (Greenhouse, Lever, Ashby)."""

import httpx

from src.config import settings
from src.tracker.application_tracker import ApplicationTracker


class APISubmitter:
    """Submits applications programmatically via ATS APIs.
    
    Supported platforms:
    - Greenhouse (via candidate ingestion API)
    - Lever (via opportunities API)
    - Ashby (via candidate API)
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.tracker = ApplicationTracker()

    async def submit_greenhouse(
        self,
        application_id: str,
        job_board_token: str,
        job_id: str,
        candidate_data: dict,
        resume_path: str,
    ) -> dict:
        """Submit application via Greenhouse candidate ingestion API."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{job_board_token}/jobs/{job_id}"

        # Prepare multipart form data
        files = {}
        if resume_path:
            files["resume"] = open(resume_path, "rb")

        data = {
            "first_name": candidate_data.get("first_name", ""),
            "last_name": candidate_data.get("last_name", ""),
            "email": candidate_data.get("email", ""),
            "phone": candidate_data.get("phone", ""),
            "linkedin_profile_url": candidate_data.get("linkedin", ""),
            "website_url": candidate_data.get("website", ""),
        }

        headers = {}
        if settings.greenhouse_api_token:
            headers["Authorization"] = f"Basic {settings.greenhouse_api_token}"

        try:
            response = await self.client.post(url, data=data, files=files, headers=headers)
            response.raise_for_status()

            from uuid import UUID
            await self.tracker.mark_submitted(UUID(application_id), method="api_greenhouse")

            return {
                "success": True,
                "platform": "greenhouse",
                "response": response.json() if response.content else {},
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "platform": "greenhouse",
                "error": str(e),
                "status_code": e.response.status_code,
            }
        finally:
            if files:
                for f in files.values():
                    f.close()

    async def submit_lever(
        self,
        application_id: str,
        company_slug: str,
        posting_id: str,
        candidate_data: dict,
        resume_path: str,
    ) -> dict:
        """Submit application via Lever postings API."""
        url = f"https://api.lever.co/v0/postings/{company_slug}/{posting_id}/apply"

        files = {}
        if resume_path:
            files["resume"] = open(resume_path, "rb")

        data = {
            "name": candidate_data.get("full_name", ""),
            "email": candidate_data.get("email", ""),
            "phone": candidate_data.get("phone", ""),
            "urls[LinkedIn]": candidate_data.get("linkedin", ""),
            "urls[GitHub]": candidate_data.get("github", ""),
            "urls[Portfolio]": candidate_data.get("website", ""),
            "comments": candidate_data.get("cover_letter", ""),
        }

        try:
            response = await self.client.post(url, data=data, files=files)
            response.raise_for_status()

            from uuid import UUID
            await self.tracker.mark_submitted(UUID(application_id), method="api_lever")

            return {
                "success": True,
                "platform": "lever",
                "response": response.json() if response.content else {},
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "platform": "lever",
                "error": str(e),
                "status_code": e.response.status_code,
            }
        finally:
            if files:
                for f in files.values():
                    f.close()

    async def submit_ashby(
        self,
        application_id: str,
        job_posting_id: str,
        candidate_data: dict,
        resume_path: str,
    ) -> dict:
        """Submit application via Ashby API."""
        url = "https://api.ashbyhq.com/applicationForm.submit"

        headers = {
            "Content-Type": "application/json",
        }
        if settings.ashby_api_key:
            headers["Authorization"] = f"Basic {settings.ashby_api_key}"

        payload = {
            "applicationForm": {
                "jobPostingId": job_posting_id,
                "fieldSubmissions": [
                    {"fieldId": "_systemfield_name", "value": candidate_data.get("full_name", "")},
                    {"fieldId": "_systemfield_email", "value": candidate_data.get("email", "")},
                    {"fieldId": "_systemfield_phone", "value": candidate_data.get("phone", "")},
                    {
                        "fieldId": "_systemfield_linkedin",
                        "value": candidate_data.get("linkedin", ""),
                    },
                ],
            }
        }

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            from uuid import UUID
            await self.tracker.mark_submitted(UUID(application_id), method="api_ashby")

            return {
                "success": True,
                "platform": "ashby",
                "response": response.json() if response.content else {},
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "platform": "ashby",
                "error": str(e),
                "status_code": e.response.status_code,
            }
