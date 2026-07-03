"""Application Logger - Logs every application to CSV and optionally Google Sheets.

This gives you a simple, always-accessible record of:
- What jobs you applied to
- Which tailored resume version was used
- What keywords were added
- The score and status
- Direct path to open the resume file

You can always open data/applications_log.csv in Excel/Google Sheets to review everything.
"""

import csv
from datetime import datetime
from pathlib import Path

from src.config import settings


class ApplicationLogger:
    """Logs all applications to a CSV file for easy tracking and review.
    
    Columns:
    - date: When the application was created
    - company: Company name
    - role: Job title
    - location: Job location
    - fit_score: How well it matched (0-1)
    - recommendation: apply/maybe/skip
    - resume_path: Full path to the tailored DOCX (open in Word to review)
    - ats_score: Estimated ATS compatibility %
    - keywords_added: What keywords were injected into your resume
    - sections_modified: Which sections were changed
    - status: pending_review/approved/submitted/interview/rejected/offer
    - source: Where the job was found (greenhouse/lever/linkedin/etc.)
    - url: Link to the original job posting
    - notes: Any additional notes
    """

    CSV_PATH = Path("data/applications_log.csv")

    HEADERS = [
        "date",
        "company",
        "role",
        "location",
        "fit_score",
        "recommendation",
        "resume_path",
        "ats_score",
        "keywords_added",
        "sections_modified",
        "status",
        "source",
        "url",
        "notes",
    ]

    def __init__(self):
        self.CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not self.CSV_PATH.exists():
            self._create_csv()

    def _create_csv(self):
        """Create CSV with headers."""
        with open(self.CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.HEADERS)

    def log_application(
        self,
        company: str,
        role: str,
        location: str = "",
        fit_score: float = 0.0,
        recommendation: str = "",
        resume_path: str = "",
        ats_score: float = 0.0,
        keywords_added: list[str] | None = None,
        sections_modified: list[str] | None = None,
        status: str = "pending_review",
        source: str = "",
        url: str = "",
        notes: str = "",
    ):
        """Log a single application to CSV."""
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            company,
            role,
            location,
            f"{fit_score:.2f}",
            recommendation,
            resume_path,
            f"{ats_score:.0%}",
            ", ".join(keywords_added) if keywords_added else "",
            ", ".join(sections_modified) if sections_modified else "",
            status,
            source,
            url,
            notes,
        ]

        with open(self.CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def update_status(self, company: str, role: str, new_status: str):
        """Update the status of an existing application."""
        rows = self._read_all()
        updated = False

        for row in rows:
            if row[1] == company and row[2] == role:
                row[10] = new_status  # status column index
                updated = True
                break

        if updated:
            self._write_all(rows)

    def get_all_applications(self) -> list[dict]:
        """Read all applications as list of dicts."""
        rows = self._read_all()
        return [dict(zip(self.HEADERS, row)) for row in rows[1:]]  # Skip header

    def get_by_status(self, status: str) -> list[dict]:
        """Get applications filtered by status."""
        all_apps = self.get_all_applications()
        return [app for app in all_apps if app["status"] == status]

    def get_summary(self) -> dict:
        """Get summary counts by status."""
        all_apps = self.get_all_applications()
        summary = {}
        for app in all_apps:
            status = app.get("status", "unknown")
            summary[status] = summary.get(status, 0) + 1
        summary["total"] = len(all_apps)
        return summary

    def _read_all(self) -> list[list[str]]:
        """Read all rows from CSV."""
        with open(self.CSV_PATH, "r", encoding="utf-8") as f:
            return list(csv.reader(f))

    def _write_all(self, rows: list[list[str]]):
        """Write all rows back to CSV."""
        with open(self.CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
