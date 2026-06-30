"""Human Review Queue - Presents tailored resumes for approval before submission."""

from datetime import datetime
from uuid import UUID

from src.tracker.application_tracker import ApplicationTracker
from src.resume.tailoring_agent import TailoringResult


class ReviewQueue:
    """Manages the human review workflow.
    
    Flow:
    1. Resume is tailored by the agent
    2. Application enters review queue with tailored resume attached
    3. Human reviews diff, approves/edits/rejects
    4. Approved applications move to submission
    5. Feedback from rejections feeds back to scoring model
    """

    def __init__(self):
        self.tracker = ApplicationTracker()

    async def add_to_queue(
        self,
        job_id: UUID,
        tailoring_result: TailoringResult,
    ) -> dict:
        """Add a tailored application to the review queue."""
        application = await self.tracker.create_application(
            job_id=job_id,
            resume_version=f"v_{datetime.now().strftime('%Y%m%d_%H%M')}",
            resume_path=tailoring_result.output_path,
        )

        return {
            "application_id": str(application.id),
            "job_id": str(job_id),
            "company": tailoring_result.company,
            "title": tailoring_result.title,
            "resume_path": tailoring_result.output_path,
            "ats_score": tailoring_result.ats_score_estimate,
            "keywords_matched": tailoring_result.keywords_matched,
            "keywords_added": tailoring_result.keywords_added,
            "sections_modified": [s.section_name for s in tailoring_result.sections_modified],
            "status": "pending_review",
        }

    async def get_daily_queue(self) -> list[dict]:
        """Get all items pending review (daily batch)."""
        return await self.tracker.get_pending_review()

    async def approve(self, application_id: UUID) -> dict:
        """Approve an application for submission."""
        app = await self.tracker.approve_application(application_id)
        return {
            "application_id": str(app.id),
            "status": "approved",
            "message": "Application approved for submission.",
        }

    async def reject(self, application_id: UUID, reason: str) -> dict:
        """Reject an application (won't be submitted)."""
        app = await self.tracker.update_status(
            application_id, status="rejected", notes=f"Rejected in review: {reason}"
        )
        return {
            "application_id": str(app.id),
            "status": "rejected",
            "reason": reason,
        }

    async def get_review_diff(self, application_id: UUID) -> dict:
        """Get the diff between original and tailored resume for review."""
        # This would load the original template and the tailored version
        # and show a side-by-side comparison
        pending = await self.tracker.get_pending_review()
        for item in pending:
            if item["application_id"] == str(application_id):
                return {
                    "application_id": str(application_id),
                    "company": item["company"],
                    "title": item["title"],
                    "resume_path": item["resume_path"],
                    "fit_score": item["fit_score"],
                }
        return {"error": "Application not found in review queue"}
