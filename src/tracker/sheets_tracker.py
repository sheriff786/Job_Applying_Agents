"""Google Sheets Tracker - Syncs application data to a Google Sheet.

This allows you to:
- View all applications from ANY device (phone, laptop, anywhere)
- Share with others for accountability
- See real-time status updates
- Filter/sort/search in Google Sheets UI

Setup:
1. Create a Google Sheet
2. Share it with your service account email
3. Add GOOGLE_SHEET_ID to .env
"""

from datetime import datetime
from pathlib import Path

from src.config import settings


class GoogleSheetsTracker:
    """Syncs application data to Google Sheets for easy access anywhere.
    
    Sheet structure:
    Row 1: Headers
    Row 2+: One row per application
    
    Columns: Date | Company | Role | Location | Score | Resume Link | ATS% | 
             Keywords Added | Status | Source | Job URL | Notes
    """

    HEADERS = [
        "Date",
        "Company",
        "Role",
        "Location",
        "Fit Score",
        "Resume File",
        "ATS Score",
        "Keywords Added",
        "Sections Modified",
        "Status",
        "Source",
        "Job URL",
        "Notes",
    ]

    def __init__(self):
        self.sheet_id = getattr(settings, "google_sheet_id", "")
        self.credentials_path = Path(settings.google_credentials_file)

    async def log_application(
        self,
        company: str,
        role: str,
        location: str = "",
        fit_score: float = 0.0,
        resume_path: str = "",
        ats_score: float = 0.0,
        keywords_added: list[str] | None = None,
        sections_modified: list[str] | None = None,
        status: str = "pending_review",
        source: str = "",
        url: str = "",
        notes: str = "",
    ) -> bool:
        """Add a new application row to Google Sheet."""
        try:
            service = self._get_sheets_service()
            if not service:
                return False

            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                company,
                role,
                location,
                f"{fit_score:.2f}",
                resume_path,
                f"{ats_score:.0%}",
                ", ".join(keywords_added) if keywords_added else "",
                ", ".join(sections_modified) if sections_modified else "",
                status,
                source,
                url,
                notes,
            ]

            body = {"values": [row]}
            service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range="Sheet1!A:M",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()

            return True
        except Exception:
            return False

    async def update_status(self, company: str, role: str, new_status: str) -> bool:
        """Update status column for an existing application."""
        try:
            service = self._get_sheets_service()
            if not service:
                return False

            # Read all data to find the row
            result = service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range="Sheet1!A:M",
            ).execute()

            rows = result.get("values", [])
            for i, row in enumerate(rows[1:], start=2):  # Skip header
                if len(row) >= 3 and row[1] == company and row[2] == role:
                    # Update status column (index 9 = column J)
                    service.spreadsheets().values().update(
                        spreadsheetId=self.sheet_id,
                        range=f"Sheet1!J{i}",
                        valueInputOption="USER_ENTERED",
                        body={"values": [[new_status]]},
                    ).execute()
                    return True

            return False
        except Exception:
            return False

    async def setup_sheet(self) -> bool:
        """Initialize the Google Sheet with headers and formatting."""
        try:
            service = self._get_sheets_service()
            if not service:
                return False

            # Write headers
            body = {"values": [self.HEADERS]}
            service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range="Sheet1!A1:M1",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()

            # Bold headers and freeze first row
            requests = [
                {
                    "repeatCell": {
                        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": 0,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]

            service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests},
            ).execute()

            return True
        except Exception:
            return False

    def _get_sheets_service(self):
        """Initialize Google Sheets API service."""
        if not self.sheet_id or not self.credentials_path.exists():
            return None

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(str(self.credentials_path))
            return build("sheets", "v4", credentials=creds)
        except Exception:
            return None
