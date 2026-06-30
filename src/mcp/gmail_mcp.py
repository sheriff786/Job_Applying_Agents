"""Gmail MCP - Detects status reply emails from companies."""

import base64
import re
from datetime import datetime
from pathlib import Path

from src.config import settings


class GmailMCP:
    """Monitors Gmail for application status updates.
    
    Detects:
    - Rejection emails
    - Interview invitation emails
    - Offer emails
    - Assessment/coding challenge emails
    """

    # Common patterns in recruitment emails
    REJECTION_PATTERNS = [
        r"we(?:'ve| have) decided (?:to )?(?:not )?(?:move|proceed) (?:forward )?with other",
        r"unfortunately.*(?:not|won't) (?:be )?(?:moving|proceeding) forward",
        r"after careful consideration.*(?:not|won't) be (?:moving|proceeding)",
        r"we(?:'ve| have) decided to pursue other candidates",
        r"position has been filled",
        r"not a match at this time",
    ]

    INTERVIEW_PATTERNS = [
        r"(?:schedule|book).*interview",
        r"(?:like|love) to (?:speak|chat|meet|connect) with you",
        r"next (?:step|round|stage)",
        r"(?:phone|video|onsite|technical) (?:screen|interview|round)",
        r"calendly\.com|zoom\.us.*meeting",
    ]

    OFFER_PATTERNS = [
        r"(?:pleased|excited|happy) to (?:offer|extend)",
        r"offer (?:letter|of employment)",
        r"compensation package",
    ]

    def __init__(self):
        self.credentials_path = Path(settings.gmail_credentials_file)

    async def check_for_updates(self) -> list[dict]:
        """Check Gmail for application status updates.
        
        Returns list of detected status changes.
        Note: Requires Google OAuth setup. See credentials setup in README.
        """
        # This requires google-api-python-client with OAuth credentials
        # Skeleton implementation - requires user to set up Google OAuth
        try:
            service = await self._get_gmail_service()
            messages = await self._fetch_recent_messages(service)
            updates = []

            for msg in messages:
                status = self._classify_email(msg)
                if status:
                    updates.append({
                        "email_id": msg["id"],
                        "from": msg["from"],
                        "subject": msg["subject"],
                        "date": msg["date"],
                        "detected_status": status,
                        "company": self._extract_company(msg["from"], msg["subject"]),
                    })

            return updates
        except Exception:
            # If credentials aren't set up, return empty
            return []

    async def _get_gmail_service(self):
        """Initialize Gmail API service with OAuth."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not self.credentials_path.exists():
            raise FileNotFoundError("Gmail credentials not configured")

        creds = Credentials.from_authorized_user_file(str(self.credentials_path))
        return build("gmail", "v1", credentials=creds)

    async def _fetch_recent_messages(self, service, max_results: int = 50) -> list[dict]:
        """Fetch recent messages that might be from recruiters."""
        # Search for emails from common ATS/recruiting domains
        query = (
            "from:(greenhouse.io OR lever.co OR ashbyhq.com OR "
            "jobs- OR talent OR recruiting OR careers OR hr@)"
        )

        results = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()

        messages = []
        for msg_ref in results.get("messages", []):
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            body = self._get_message_body(msg)

            messages.append({
                "id": msg_ref["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "body": body,
            })

        return messages

    def _get_message_body(self, msg: dict) -> str:
        """Extract text body from Gmail message."""
        payload = msg.get("payload", {})
        parts = payload.get("parts", [])

        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        return ""

    def _classify_email(self, msg: dict) -> str | None:
        """Classify email as rejection, interview, or offer."""
        text = f"{msg.get('subject', '')} {msg.get('body', '')}".lower()

        for pattern in self.OFFER_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "offer"

        for pattern in self.INTERVIEW_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "interview"

        for pattern in self.REJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "rejected"

        return None

    def _extract_company(self, from_addr: str, subject: str) -> str:
        """Try to extract company name from email."""
        # From domain
        match = re.search(r"@([^.]+)\.", from_addr)
        if match:
            domain = match.group(1)
            if domain not in ("gmail", "outlook", "yahoo", "greenhouse", "lever"):
                return domain.capitalize()

        # From subject
        match = re.search(r"(?:at|from|with) ([A-Z][a-zA-Z]+)", subject)
        if match:
            return match.group(1)

        return "Unknown"
