"""Main Pipeline Orchestrator - Coordinates the entire job application workflow."""

import asyncio
from pathlib import Path
from uuid import UUID

from rich.console import Console
from rich.table import Table

from src.config import settings
from src.database import init_db, async_session, Job
from src.ingestion.orchestrator import IngestionOrchestrator
from src.parser.jd_parser import JDParser
from src.vectorstore.store import VectorStore
from src.scoring.fit_scorer import FitScoringAgent
from src.resume.tailoring_agent import ResumeTailoringAgent
from src.resume.formatter import ResumeFormatter
from src.review.review_queue import ReviewQueue
from src.submit.api_submit import APISubmitter
from src.submit.manual_submit import ManualSubmitHelper
from src.tracker.application_tracker import ApplicationTracker
from src.mcp.gmail_mcp import GmailMCP
from src.mcp.calendar_mcp import CalendarMCP

from sqlalchemy import select, update

console = Console()


class JobAgentPipeline:
    """Main orchestrator that runs the complete job application pipeline.
    
    Pipeline stages:
    1. Ingest jobs from all sources
    2. Parse job descriptions (extract skills, level, etc.)
    3. Generate embeddings and store in vector DB
    4. Score fit against user profile
    5. Tailor resume for high-scoring jobs
    6. Queue for human review
    7. Submit approved applications
    8. Track and monitor responses
    """

    def __init__(self, user_profile_path: str):
        self.user_profile_path = Path(user_profile_path)
        self.user_profile = self._load_user_profile()

        # Initialize all agents
        self.ingestion = IngestionOrchestrator()
        self.parser = JDParser()
        self.vectorstore = VectorStore()
        self.scorer = FitScoringAgent(user_profile=self.user_profile)
        self.tailoring = ResumeTailoringAgent()
        self.formatter = ResumeFormatter(settings.resume_template_path)
        self.review = ReviewQueue()
        self.api_submitter = APISubmitter()
        self.manual_helper = ManualSubmitHelper()
        self.tracker = ApplicationTracker()
        self.gmail = GmailMCP()
        self.calendar = CalendarMCP()

    def _load_user_profile(self) -> str:
        """Load user profile for scoring."""
        if self.user_profile_path.exists():
            return self.user_profile_path.read_text(encoding="utf-8")
        return ""

    async def run_full_pipeline(self, query: str, location: str | None = None):
        """Execute the complete pipeline end-to-end."""
        console.print("\n[bold blue]🚀 Starting Job Application Pipeline[/bold blue]\n")

        # Stage 1: Initialize DB
        await init_db()
        await self.vectorstore.setup_pgvector()

        # Stage 2: Ingest jobs
        console.print("[cyan]📥 Stage 1: Ingesting jobs...[/cyan]")
        stats = await self.ingestion.ingest_all(query, location)
        console.print(f"   Fetched: {stats['fetched']}, New: {stats['new']}, "
                      f"Duplicates: {stats['duplicates']}")
        if stats["errors"]:
            for err in stats["errors"]:
                console.print(f"   [yellow]⚠ {err}[/yellow]")

        # Stage 3: Parse and embed new jobs
        console.print("[cyan]🔍 Stage 2: Parsing job descriptions...[/cyan]")
        await self._parse_new_jobs()

        # Stage 4: Score all unparsed jobs
        console.print("[cyan]📊 Stage 3: Scoring fit...[/cyan]")
        scored = await self._score_jobs()
        console.print(f"   Scored {scored} jobs")

        # Stage 5: Tailor resumes for high-scoring jobs
        console.print("[cyan]✍️  Stage 4: Tailoring resumes...[/cyan]")
        tailored = await self._tailor_for_top_jobs()
        console.print(f"   Tailored {tailored} resumes")

        # Stage 6: Check for email updates
        console.print("[cyan]📧 Stage 5: Checking email updates...[/cyan]")
        await self._check_email_updates()

        # Stage 7: Show summary
        await self._print_summary()

    async def _parse_new_jobs(self):
        """Parse all jobs that haven't been parsed yet."""
        async with async_session() as session:
            result = await session.execute(
                select(Job).where(Job.status == "new").limit(50)
            )
            jobs = result.scalars().all()

            for job in jobs:
                try:
                    parsed = await self.parser.parse(
                        company=job.company,
                        title=job.title,
                        description=job.description_raw,
                    )

                    # Update job with parsed data
                    job.skills = parsed.skills_required + parsed.skills_preferred
                    job.tech_stack = parsed.tech_stack
                    job.seniority_level = parsed.seniority_level
                    job.parsed_data = parsed.model_dump()

                    # Generate and store embedding
                    await self.vectorstore.store_job_embedding(
                        job_id=str(job.id),
                        description=job.description_raw,
                        skills=parsed.skills_required,
                    )

                    job.status = "parsed"
                    console.print(f"   ✓ Parsed: {job.company} - {job.title}")
                except Exception as e:
                    console.print(f"   [red]✗ Failed: {job.company} - {job.title}: {e}[/red]")

            await session.commit()

    async def _score_jobs(self) -> int:
        """Score all parsed jobs."""
        scored_count = 0
        async with async_session() as session:
            result = await session.execute(
                select(Job).where(Job.status == "parsed").limit(50)
            )
            jobs = result.scalars().all()

            for job in jobs:
                try:
                    from src.parser.jd_parser import ParsedJobDescription

                    parsed_jd = ParsedJobDescription(**job.parsed_data)
                    score = await self.scorer.score(
                        company=job.company,
                        title=job.title,
                        parsed_jd=parsed_jd,
                    )

                    job.fit_score = score.overall_score
                    job.fit_reasoning = score.reasoning
                    job.status = "scored"
                    scored_count += 1

                    emoji = "🟢" if score.overall_score >= settings.fit_score_threshold else "🔴"
                    console.print(
                        f"   {emoji} {job.company} - {job.title}: "
                        f"{score.overall_score:.2f} ({score.recommendation})"
                    )
                except Exception as e:
                    console.print(f"   [red]✗ Score failed: {job.company}: {e}[/red]")

            await session.commit()

        return scored_count

    async def _tailor_for_top_jobs(self) -> int:
        """Tailor resumes for jobs above the fit threshold."""
        tailored_count = 0
        async with async_session() as session:
            result = await session.execute(
                select(Job)
                .where(Job.status == "scored")
                .where(Job.fit_score >= settings.fit_score_threshold)
                .order_by(Job.fit_score.desc())
                .limit(10)
            )
            jobs = result.scalars().all()

            resume_sections = self.formatter.read_sections()

            for job in jobs:
                try:
                    from src.parser.jd_parser import ParsedJobDescription
                    from src.scoring.fit_scorer import FitScore

                    parsed_jd = ParsedJobDescription(**job.parsed_data)
                    fit_score = FitScore(
                        overall_score=job.fit_score,
                        skill_match_score=0.0,
                        seniority_match_score=0.0,
                        location_match_score=0.0,
                        company_type_score=0.0,
                        reasoning=job.fit_reasoning or "",
                        matched_skills=[],
                        missing_skills=[],
                        recommendation="apply",
                    )

                    tailoring_result = await self.tailoring.tailor_resume(
                        job_id=str(job.id),
                        company=job.company,
                        title=job.title,
                        parsed_jd=parsed_jd,
                        fit_score=fit_score,
                        resume_sections=resume_sections,
                    )

                    # Write the tailored DOCX
                    self.formatter.write_tailored_resume(tailoring_result)

                    # Add to review queue
                    await self.review.add_to_queue(
                        job_id=job.id,
                        tailoring_result=tailoring_result,
                    )

                    job.status = "tailored"
                    tailored_count += 1
                    console.print(
                        f"   ✓ Tailored: {job.company} - {job.title} "
                        f"(ATS: {tailoring_result.ats_score_estimate:.0%})"
                    )
                except Exception as e:
                    console.print(f"   [red]✗ Tailoring failed: {job.company}: {e}[/red]")

            await session.commit()

        return tailored_count

    async def _check_email_updates(self):
        """Check Gmail for application status updates."""
        updates = await self.gmail.check_for_updates()
        for update in updates:
            console.print(
                f"   📬 {update['company']}: {update['detected_status']} "
                f"({update['subject'][:50]})"
            )

            # If interview detected, create calendar hold
            if update["detected_status"] == "interview":
                await self.calendar.create_interview_hold(
                    company=update["company"],
                    role="",  # Would need to look up from tracker
                )

    async def _print_summary(self):
        """Print pipeline execution summary."""
        stats = await self.tracker.get_stats()

        console.print("\n[bold green]📊 Pipeline Summary[/bold green]")
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="white")

        table.add_row("Total Applications", str(stats["total_applications"]))
        table.add_row("Pending Review", str(stats["pending_review"]))
        table.add_row("Submitted", str(stats["submitted"]))
        table.add_row("Interviews", str(stats["interviews"]))
        table.add_row("Rejected", str(stats["rejected"]))
        table.add_row("Offers", str(stats["offers"]))

        console.print(table)

    async def submit_approved(self):
        """Submit all approved applications."""
        async with async_session() as session:
            from src.database import Application

            result = await session.execute(
                select(Application, Job)
                .join(Job, Application.job_id == Job.id)
                .where(Application.status == "approved")
            )
            rows = result.all()

            for app, job in rows:
                if job.source in ("greenhouse", "lever", "ashby"):
                    # API submission
                    console.print(f"   🚀 Auto-submitting: {job.company} - {job.title}")
                    # Would call appropriate API submitter
                else:
                    # Manual submission
                    instructions = self.manual_helper.generate_instructions(
                        platform=job.source,
                        job_url=job.url or "",
                        resume_path=app.resume_path or "",
                        company=job.company,
                        title=job.title,
                    )
                    console.print(
                        f"   📋 Manual submit needed: {job.company} - {job.title}"
                    )
                    for step in instructions.steps:
                        console.print(f"      {step}")
