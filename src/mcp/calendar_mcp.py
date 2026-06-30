"""Calendar MCP - Auto-creates interview holds when interviews are detected."""

import re
from datetime import datetime, timedelta
from pathlib import Path

from src.config import settings


class CalendarMCP:
    """Creates calendar holds when interview invitations are detected.
    
    Integrates with Google Calendar to:
    - Create interview prep blocks
    - Add interview events with meeting links
    - Set reminders
    """

    def __init__(self):
        self.credentials_path = Path(settings.calendar_credentials_file)

    async def create_interview_hold(
        self,
        company: str,
        role: str,
        interview_date: datetime | None = None,
        meeting_link: str | None = None,
        interview_type: str = "Phone Screen",
        duration_minutes: int = 60,
    ) -> dict:
        """Create a calendar event for an interview."""
        try:
            service = await self._get_calendar_service()

            # If no date provided, create a placeholder for next week
            if not interview_date:
                interview_date = datetime.now() + timedelta(days=7)

            event = {
                "summary": f"🎯 Interview: {role} @ {company} ({interview_type})",
                "description": (
                    f"Interview for {role} at {company}\n"
                    f"Type: {interview_type}\n"
                    f"Meeting Link: {meeting_link or 'TBD'}\n\n"
                    f"--- PREP NOTES ---\n"
                    f"• Research {company} recent news\n"
                    f"• Review job description keywords\n"
                    f"• Prepare STAR stories\n"
                    f"• Test meeting link 5 min before"
                ),
                "start": {
                    "dateTime": interview_date.isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": (
                        interview_date + timedelta(minutes=duration_minutes)
                    ).isoformat(),
                    "timeZone": "UTC",
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 60},  # 1 hour before
                        {"method": "popup", "minutes": 15},  # 15 min before
                        {"method": "email", "minutes": 1440},  # 1 day before
                    ],
                },
                "colorId": "11",  # Red/important
            }

            if meeting_link:
                event["conferenceData"] = {
                    "entryPoints": [{"entryPointType": "video", "uri": meeting_link}]
                }

            result = service.events().insert(calendarId="primary", body=event).execute()

            # Also create a prep block 1 hour before
            prep_event = {
                "summary": f"📝 Interview Prep: {company}",
                "description": f"Prepare for interview at {company} for {role}",
                "start": {
                    "dateTime": (interview_date - timedelta(hours=1)).isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": interview_date.isoformat(),
                    "timeZone": "UTC",
                },
                "colorId": "5",  # Yellow
            }
            service.events().insert(calendarId="primary", body=prep_event).execute()

            return {
                "success": True,
                "event_id": result.get("id"),
                "event_link": result.get("htmlLink"),
                "interview_date": interview_date.isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _get_calendar_service(self):
        """Initialize Google Calendar API service."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not self.credentials_path.exists():
            raise FileNotFoundError("Calendar credentials not configured")

        creds = Credentials.from_authorized_user_file(str(self.credentials_path))
        return build("calendar", "v3", credentials=creds)

    def extract_interview_datetime(self, email_body: str) -> datetime | None:
        """Try to extract interview date/time from email text."""
        # Common date patterns in interview emails
        patterns = [
            r"(\w+ \d{1,2},? \d{4})\s+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))",
            r"(\d{1,2}/\d{1,2}/\d{4})\s+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))",
            r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, email_body)
            if match:
                try:
                    date_str = f"{match.group(1)} {match.group(2)}"
                    for fmt in [
                        "%B %d, %Y %I:%M %p",
                        "%B %d %Y %I:%M %p",
                        "%m/%d/%Y %I:%M %p",
                        "%Y-%m-%d %H:%M",
                    ]:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                except (ValueError, IndexError):
                    continue

        return None

    def extract_meeting_link(self, email_body: str) -> str | None:
        """Extract meeting/video call link from email."""
        patterns = [
            r"(https?://[^\s]*zoom\.us/[^\s]+)",
            r"(https?://meet\.google\.com/[^\s]+)",
            r"(https?://teams\.microsoft\.com/[^\s]+)",
            r"(https?://[^\s]*calendly\.com/[^\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, email_body)
            if match:
                return match.group(1)

        return None
