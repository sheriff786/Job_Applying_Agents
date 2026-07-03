"""FastAPI web interface for the Job Applying Agent."""

import os
import sys
from datetime import datetime
from uuid import UUID
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import settings

app = FastAPI(
    title="Job Applying Agent API",
    description="Automated job application system targeting MAANG/FAANG companies outside India",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow CORS for frontend/testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ─────────────────────────────────────────

class ApproveRequest(BaseModel):
    application_id: str


class RejectRequest(BaseModel):
    application_id: str
    reason: str


class StatusUpdateRequest(BaseModel):
    application_id: str
    status: str
    notes: str | None = None


class ParseJDRequest(BaseModel):
    company: str
    title: str
    description: str


class ScoreJobRequest(BaseModel):
    company: str
    title: str
    description: str


class TailorResumeRequest(BaseModel):
    company: str
    title: str
    description: str


# ─── Health & Status Endpoints ────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API info."""
    return {
        "name": "Job Applying Agent API",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Check health of all system components."""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {},
    }

    # Check OpenAI API key
    health["components"]["openai"] = {
        "status": "configured" if settings.openai_api_key else "missing",
        "model": settings.openai_model,
    }

    # Check database connection
    try:
        from src.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["components"]["database"] = {"status": "connected"}
    except Exception as e:
        health["components"]["database"] = {"status": "disconnected", "error": str(e)}
        health["status"] = "degraded"

    # Check Redis
    try:
        import redis as redis_lib

        r = redis_lib.from_url(settings.redis_url)
        r.ping()
        health["components"]["redis"] = {"status": "connected"}
    except Exception as e:
        health["components"]["redis"] = {"status": "disconnected", "error": str(e)}
        health["status"] = "degraded"

    # Check resume template
    template_path = Path(settings.resume_template_path)
    health["components"]["resume_template"] = {
        "status": "found" if template_path.exists() else "missing",
        "path": str(template_path),
    }

    # Check user profile
    profile_path = Path("./data/user_profile.txt")
    health["components"]["user_profile"] = {
        "status": "found" if profile_path.exists() else "missing",
        "path": str(profile_path),
    }

    # Config summary
    health["config"] = {
        "fit_score_threshold": settings.fit_score_threshold,
        "target_locations": settings.target_locations,
        "excluded_locations": settings.excluded_locations,
        "seniority_levels": settings.seniority_levels,
    }

    return health


# ─── Demo Endpoints (work without DB) ─────────────────────────────────

@app.post("/demo/parse-jd", tags=["Demo"])
async def demo_parse_jd(request: ParseJDRequest):
    """Demo: Parse a job description using GPT-4o.
    
    Send any job description and see the structured output.
    This works without database - just needs OPENAI_API_KEY.
    """
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured in .env")

    from src.parser.jd_parser import JDParser

    parser = JDParser()
    try:
        result = await parser.parse(
            company=request.company,
            title=request.title,
            description=request.description,
        )
        return {
            "status": "success",
            "parsed": result.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@app.post("/demo/score-job", tags=["Demo"])
async def demo_score_job(request: ScoreJobRequest):
    """Demo: Score a job against your profile.
    
    Send a job description and see the fit score breakdown.
    Needs OPENAI_API_KEY and data/user_profile.txt.
    """
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured in .env")

    profile_path = Path("./data/user_profile.txt")
    if not profile_path.exists():
        raise HTTPException(status_code=400, detail="data/user_profile.txt not found")

    from src.parser.jd_parser import JDParser
    from src.scoring.fit_scorer import FitScoringAgent

    # Parse JD first
    parser = JDParser()
    try:
        parsed_jd = await parser.parse(
            company=request.company,
            title=request.title,
            description=request.description,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD parsing failed: {str(e)}")

    # Score it
    user_profile = profile_path.read_text(encoding="utf-8")
    scorer = FitScoringAgent(user_profile=user_profile)
    try:
        score = await scorer.score(
            company=request.company,
            title=request.title,
            parsed_jd=parsed_jd,
        )
        return {
            "status": "success",
            "parsed_jd": parsed_jd.model_dump(),
            "fit_score": score.model_dump(),
            "should_apply": scorer.should_apply(score),
            "threshold": settings.fit_score_threshold,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@app.post("/demo/tailor-resume", tags=["Demo"])
async def demo_tailor_resume(request: TailorResumeRequest):
    """Demo: See how the resume would be tailored for a job.
    
    Returns the tailoring plan (sections to modify, keywords to add).
    Needs OPENAI_API_KEY and data/resume_template.docx.
    """
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured in .env")

    template_path = Path(settings.resume_template_path)
    if not template_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Resume template not found at {settings.resume_template_path}. "
                   "Run 'job-agent init-template' first.",
        )

    from src.parser.jd_parser import JDParser
    from src.scoring.fit_scorer import FitScoringAgent, FitScore
    from src.resume.tailoring_agent import ResumeTailoringAgent
    from src.resume.formatter import ResumeFormatter

    # Parse JD
    parser = JDParser()
    try:
        parsed_jd = await parser.parse(
            company=request.company,
            title=request.title,
            description=request.description,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD parsing failed: {str(e)}")

    # Score
    profile_path = Path("./data/user_profile.txt")
    user_profile = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
    scorer = FitScoringAgent(user_profile=user_profile)
    try:
        score = await scorer.score(
            company=request.company, title=request.title, parsed_jd=parsed_jd
        )
    except Exception:
        score = FitScore(
            overall_score=0.8, skill_match_score=0.8, seniority_match_score=0.8,
            location_match_score=1.0, company_type_score=0.8,
            reasoning="Score estimation", matched_skills=[], missing_skills=[],
            recommendation="apply",
        )

    # Read template sections
    formatter = ResumeFormatter(settings.resume_template_path)
    resume_sections = formatter.read_sections()

    # Tailor
    tailoring_agent = ResumeTailoringAgent()
    try:
        result = await tailoring_agent.tailor_resume(
            job_id="demo-job",
            company=request.company,
            title=request.title,
            parsed_jd=parsed_jd,
            fit_score=score,
            resume_sections=resume_sections,
        )

        # Write the actual DOCX
        output_path = formatter.write_tailored_resume(result)

        return {
            "status": "success",
            "output_path": output_path,
            "ats_score_estimate": result.ats_score_estimate,
            "keywords_matched": result.keywords_matched,
            "keywords_added": result.keywords_added,
            "sections_modified": [
                {
                    "section": s.section_name,
                    "keywords_added": s.keywords_added,
                    "changes_made": s.changes_made,
                    "tailored_preview": s.tailored_content[:300] + "..."
                    if len(s.tailored_content) > 300 else s.tailored_content,
                }
                for s in result.sections_modified
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")


@app.get("/demo/ingestion-test", tags=["Demo"])
async def demo_ingestion_test():
    """Demo: Test job fetching from RemoteOK (free, no API key needed).
    
    Fetches a few software engineering jobs to verify ingestion works.
    """
    from src.ingestion.remoteok import RemoteOKFetcher

    fetcher = RemoteOKFetcher()
    try:
        jobs = await fetcher.fetch_jobs("engineer")
        return {
            "status": "success",
            "source": "RemoteOK",
            "jobs_found": len(jobs),
            "sample_jobs": [
                {
                    "company": j.company,
                    "title": j.title,
                    "location": j.location,
                    "remote": j.remote,
                    "url": j.url,
                }
                for j in jobs[:10]  # Show first 10
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion test failed: {str(e)}")


@app.get("/demo/skills-check", tags=["Demo"])
async def demo_skills_check():
    """Demo: Show configured target companies and skill matching logic."""
    from src.resume.skills import (
        MAANG_COMPANIES,
        FAANG_COMPANIES,
        PRODUCT_COMPANIES,
        is_target_company,
        calculate_skill_overlap,
    )

    # Example skill match
    sample_candidate = ["Python", "React", "Kubernetes", "PostgreSQL", "AWS", "TypeScript"]
    sample_jd = ["Python", "Go", "Kubernetes", "Docker", "gRPC", "PostgreSQL", "CI/CD"]

    overlap = calculate_skill_overlap(sample_candidate, sample_jd)

    return {
        "target_companies": {
            "maang": sorted(MAANG_COMPANIES),
            "faang": sorted(FAANG_COMPANIES),
            "product_based": sorted(list(PRODUCT_COMPANIES)[:20]) + ["... and more"],
        },
        "example_skill_match": {
            "candidate_skills": sample_candidate,
            "jd_required_skills": sample_jd,
            "matched": overlap["matched"],
            "missing": overlap["missing"],
            "match_ratio": round(overlap["match_ratio"], 2),
        },
        "company_checks": {
            "Google": is_target_company("Google"),
            "Stripe": is_target_company("Stripe"),
            "Random Startup": is_target_company("Random Startup"),
        },
    }


@app.get("/demo/apify-status", tags=["Demo"])
async def demo_apify_status():
    """Check if Apify integration is configured and show what it enables.
    
    Apify allows scraping LinkedIn and Indeed jobs at scale.
    Without it, we rely on Greenhouse/Lever APIs + RemoteOK + manual LinkedIn exports.
    """
    apify_configured = bool(settings.apify_api_token)

    sources_available = {
        "greenhouse_api": {"status": "always_available", "jobs_per_run": "~200"},
        "lever_api": {"status": "always_available", "jobs_per_run": "~100"},
        "remoteok_api": {"status": "always_available", "jobs_per_run": "~50"},
        "wellfound_scraping": {"status": "always_available", "jobs_per_run": "~30"},
        "linkedin_manual_export": {"status": "always_available", "jobs_per_run": "varies"},
        "linkedin_apify": {
            "status": "active" if apify_configured else "needs_APIFY_API_TOKEN",
            "jobs_per_run": "~100",
            "note": "Scrapes LinkedIn job listings with full descriptions",
        },
        "indeed_apify": {
            "status": "active" if apify_configured else "needs_APIFY_API_TOKEN",
            "jobs_per_run": "~50",
            "note": "Scrapes Indeed job listings",
        },
    }

    return {
        "apify_configured": apify_configured,
        "sources": sources_available,
        "total_jobs_per_pipeline_run": "500+" if apify_configured else "~380",
        "setup_instructions": {
            "1": "Sign up at https://apify.com (free tier: 30 runs/month)",
            "2": "Go to Settings → Integrations → API Token",
            "3": "Add APIFY_API_TOKEN=your_token to .env file",
            "4": "Restart the server - LinkedIn/Indeed scraping will auto-enable",
        },
    }


class LinkedInSearchRequest(BaseModel):
    keywords: str = "Senior Software Engineer"
    location: str = "India"
    max_results: int = 20


@app.post("/demo/linkedin-search", tags=["Demo"])
async def demo_linkedin_search(request: LinkedInSearchRequest):
    """Search LinkedIn for jobs via Apify.
    
    This triggers the Apify LinkedIn Jobs Scraper actor which:
    - Searches LinkedIn with your keywords and location
    - Scrapes full job descriptions
    - Returns structured data (title, company, location, description, URL)
    
    Note: First run takes 1-3 minutes (Apify needs to spin up browsers).
    Subsequent runs are faster due to caching.
    """
    if not settings.apify_api_token:
        raise HTTPException(
            status_code=400,
            detail="Apify not configured. Add APIFY_API_TOKEN to .env file. "
                   "Sign up free at https://apify.com",
        )

    try:
        from src.ingestion.apify_scraper import ApifyLinkedInFetcher

        fetcher = ApifyLinkedInFetcher()
        jobs = await fetcher.fetch_jobs(
            query=request.keywords,
            location=request.location,
        )

        # Limit results
        jobs = jobs[:request.max_results]

        return {
            "total_found": len(jobs),
            "keywords": request.keywords,
            "location": request.location,
            "jobs": [
                {
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "remote": j.remote,
                    "url": j.url,
                    "posted_at": j.posted_at,
                    "description_preview": (j.description or "")[:200] + "...",
                }
                for j in jobs
            ],
            "note": "Full descriptions available. Use /demo/score-job to evaluate each.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apify search failed: {str(e)}")


# ─── Tracker Endpoints (need database) ────────────────────────────────

@app.get("/stats", tags=["Tracker"])
async def get_stats():
    """Get pipeline statistics. Requires database connection."""
    try:
        from src.tracker.application_tracker import ApplicationTracker
        t = ApplicationTracker()
        return await t.get_stats()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not available: {str(e)}")


@app.get("/review/pending", tags=["Review"])
async def get_pending_review():
    """Get all applications pending review. Requires database."""
    try:
        from src.review.review_queue import ReviewQueue
        r = ReviewQueue()
        return await r.get_daily_queue()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not available: {str(e)}")


@app.post("/review/approve", tags=["Review"])
async def approve_application(request: ApproveRequest):
    """Approve an application for submission."""
    try:
        from src.review.review_queue import ReviewQueue
        r = ReviewQueue()
        result = await r.approve(UUID(request.application_id))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/review/reject", tags=["Review"])
async def reject_application(request: RejectRequest):
    """Reject an application."""
    try:
        from src.review.review_queue import ReviewQueue
        r = ReviewQueue()
        result = await r.reject(UUID(request.application_id), request.reason)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/status/update", tags=["Tracker"])
async def update_status(request: StatusUpdateRequest):
    """Update application status."""
    try:
        from src.tracker.application_tracker import ApplicationTracker
        t = ApplicationTracker()
        application = await t.update_status(
            UUID(request.application_id), request.status, request.notes
        )
        return {"application_id": str(application.id), "status": application.status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/applications/{company}", tags=["Tracker"])
async def get_applications_by_company(company: str):
    """Get all applications for a company."""
    try:
        from src.tracker.application_tracker import ApplicationTracker
        t = ApplicationTracker()
        return await t.get_applications_by_company(company)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not available: {str(e)}")


# ─── CSV Log Endpoints (work without database) ────────────────────────

@app.get("/log/all", tags=["Application Log"])
async def get_all_logged_applications():
    """View ALL applications ever made — stored locally in CSV.
    
    This is your history. Shows:
    - Which companies you applied to
    - What resume version was used (file path — open in Word)
    - What keywords were added
    - Current status
    - Fit score and ATS score
    
    File location: data/applications_log.csv (open in Excel anytime)
    """
    from src.tracker.csv_logger import ApplicationLogger
    logger = ApplicationLogger()
    applications = logger.get_all_applications()
    summary = logger.get_summary()

    return {
        "total": summary.get("total", 0),
        "summary_by_status": summary,
        "applications": applications,
        "csv_file": "data/applications_log.csv (open in Excel to review)",
    }


@app.get("/log/summary", tags=["Application Log"])
async def get_application_summary():
    """Quick summary of your application pipeline."""
    from src.tracker.csv_logger import ApplicationLogger
    logger = ApplicationLogger()
    return logger.get_summary()


@app.get("/log/resumes", tags=["Application Log"])
async def get_generated_resumes():
    """List all tailored resume files you can open and cross-check.
    
    Each file is a tailored version of your resume for a specific job.
    Open any of them in Word to see exactly what was/would be submitted.
    """
    from pathlib import Path
    resume_dir = Path(settings.resume_output_dir)

    if not resume_dir.exists():
        return {"resumes": [], "directory": str(resume_dir), "message": "No resumes generated yet"}

    files = sorted(resume_dir.glob("*.docx"), key=lambda f: f.stat().st_mtime, reverse=True)

    return {
        "directory": str(resume_dir.absolute()),
        "total_resumes": len(files),
        "resumes": [
            {
                "filename": f.name,
                "full_path": str(f.absolute()),
                "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "company": f.stem.split("_")[0] if "_" in f.stem else f.stem,
            }
            for f in files
        ],
        "tip": "Open any file in Word to cross-check what was tailored for that job",
    }
