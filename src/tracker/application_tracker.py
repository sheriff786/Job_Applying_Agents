"""Application Tracker - Manages application lifecycle and status updates."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Job, Application, ResumeVersion, async_session


class ApplicationTracker:
    """Tracks applications through their entire lifecycle.
    
    Statuses: pending_review -> approved -> submitted -> [rejected | interview | offer]
    """

    async def create_application(
        self,
        job_id: UUID,
        resume_version: str,
        resume_path: str,
        cover_letter: str | None = None,
    ) -> Application:
        """Create a new application record."""
        async with async_session() as session:
            application = Application(
                job_id=job_id,
                resume_version=resume_version,
                resume_path=resume_path,
                cover_letter=cover_letter,
                status="pending_review",
            )
            session.add(application)

            # Update job status
            await session.execute(
                update(Job).where(Job.id == job_id).values(status="pending_review")
            )

            await session.commit()
            await session.refresh(application)
            return application

    async def approve_application(self, application_id: UUID) -> Application:
        """Mark application as approved for submission."""
        async with async_session() as session:
            result = await session.execute(
                select(Application).where(Application.id == application_id)
            )
            app = result.scalar_one()
            app.status = "approved"
            app.updated_at = datetime.utcnow()
            await session.commit()
            return app

    async def mark_submitted(
        self, application_id: UUID, method: str = "api"
    ) -> Application:
        """Mark application as submitted."""
        async with async_session() as session:
            result = await session.execute(
                select(Application).where(Application.id == application_id)
            )
            app = result.scalar_one()
            app.status = "submitted"
            app.submitted_at = datetime.utcnow()
            app.submission_method = method
            app.updated_at = datetime.utcnow()

            # Update job status too
            await session.execute(
                update(Job).where(Job.id == app.job_id).values(status="applied")
            )

            await session.commit()
            return app

    async def update_status(
        self, application_id: UUID, status: str, notes: str | None = None
    ) -> Application:
        """Update application status (e.g., after receiving response)."""
        async with async_session() as session:
            result = await session.execute(
                select(Application).where(Application.id == application_id)
            )
            app = result.scalar_one()
            app.status = status
            app.updated_at = datetime.utcnow()
            if notes:
                app.notes = notes
            if status in ("rejected", "interview", "offer"):
                app.response_received = True
                app.response_date = datetime.utcnow()

            # Update job status
            await session.execute(
                update(Job).where(Job.id == app.job_id).values(status=status)
            )

            await session.commit()
            return app

    async def get_pending_review(self) -> list[dict]:
        """Get all applications pending human review."""
        async with async_session() as session:
            result = await session.execute(
                select(Application, Job)
                .join(Job, Application.job_id == Job.id)
                .where(Application.status == "pending_review")
                .order_by(Application.created_at.desc())
            )
            rows = result.all()

            return [
                {
                    "application_id": str(app.id),
                    "job_id": str(job.id),
                    "company": job.company,
                    "title": job.title,
                    "location": job.location,
                    "resume_path": app.resume_path,
                    "resume_version": app.resume_version,
                    "created_at": app.created_at.isoformat(),
                    "fit_score": job.fit_score,
                }
                for app, job in rows
            ]

    async def get_stats(self) -> dict:
        """Get application pipeline statistics."""
        async with async_session() as session:
            total = await session.execute(select(func.count(Application.id)))
            pending = await session.execute(
                select(func.count(Application.id)).where(
                    Application.status == "pending_review"
                )
            )
            submitted = await session.execute(
                select(func.count(Application.id)).where(Application.status == "submitted")
            )
            interviews = await session.execute(
                select(func.count(Application.id)).where(Application.status == "interview")
            )
            rejected = await session.execute(
                select(func.count(Application.id)).where(Application.status == "rejected")
            )
            offers = await session.execute(
                select(func.count(Application.id)).where(Application.status == "offer")
            )

            return {
                "total_applications": total.scalar() or 0,
                "pending_review": pending.scalar() or 0,
                "submitted": submitted.scalar() or 0,
                "interviews": interviews.scalar() or 0,
                "rejected": rejected.scalar() or 0,
                "offers": offers.scalar() or 0,
            }

    async def get_applications_by_company(self, company: str) -> list[dict]:
        """Get all applications for a specific company."""
        async with async_session() as session:
            result = await session.execute(
                select(Application, Job)
                .join(Job, Application.job_id == Job.id)
                .where(Job.company.ilike(f"%{company}%"))
                .order_by(Application.created_at.desc())
            )
            rows = result.all()

            return [
                {
                    "application_id": str(app.id),
                    "company": job.company,
                    "title": job.title,
                    "status": app.status,
                    "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
                    "response_received": app.response_received,
                }
                for app, job in rows
            ]
