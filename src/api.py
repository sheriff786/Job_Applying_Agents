"""FastAPI web interface for the Job Applying Agent."""

from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.tracker.application_tracker import ApplicationTracker
from src.review.review_queue import ReviewQueue

app = FastAPI(
    title="Job Applying Agent API",
    description="Automated job application system targeting MAANG/FAANG companies",
    version="0.1.0",
)

tracker = ApplicationTracker()
review = ReviewQueue()


class ApproveRequest(BaseModel):
    application_id: str


class RejectRequest(BaseModel):
    application_id: str
    reason: str


class StatusUpdateRequest(BaseModel):
    application_id: str
    status: str
    notes: str | None = None


@app.get("/")
async def root():
    return {"message": "Job Applying Agent API", "version": "0.1.0"}


@app.get("/stats")
async def get_stats():
    """Get pipeline statistics."""
    return await tracker.get_stats()


@app.get("/review/pending")
async def get_pending_review():
    """Get all applications pending review."""
    return await review.get_daily_queue()


@app.post("/review/approve")
async def approve_application(request: ApproveRequest):
    """Approve an application for submission."""
    try:
        result = await review.approve(UUID(request.application_id))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/review/reject")
async def reject_application(request: RejectRequest):
    """Reject an application."""
    try:
        result = await review.reject(UUID(request.application_id), request.reason)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/status/update")
async def update_status(request: StatusUpdateRequest):
    """Update application status."""
    try:
        app = await tracker.update_status(
            UUID(request.application_id), request.status, request.notes
        )
        return {"application_id": str(app.id), "status": app.status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/applications/{company}")
async def get_applications_by_company(company: str):
    """Get all applications for a company."""
    return await tracker.get_applications_by_company(company)
