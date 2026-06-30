"""CLI interface for the Job Applying Agent."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from src.config import settings

app = typer.Typer(
    name="job-agent",
    help="Automated Job Application Agent - Target MAANG/FAANG & Product Companies",
)
console = Console()


@app.command()
def run(
    query: str = typer.Option("software engineer", help="Job search query"),
    location: str = typer.Option(None, help="Target location filter"),
    profile: str = typer.Option("./data/user_profile.txt", help="Path to user profile"),
):
    """Run the full job application pipeline."""
    console.print(
        Panel.fit(
            "[bold]Job Applying Agent[/bold]\n"
            f"Query: {query}\n"
            f"Location: {location or 'All target locations'}\n"
            f"Profile: {profile}",
            border_style="blue",
        )
    )

    from src.pipeline import JobAgentPipeline

    pipeline = JobAgentPipeline(user_profile_path=profile)
    asyncio.run(pipeline.run_full_pipeline(query=query, location=location))


@app.command()
def ingest(
    query: str = typer.Option("software engineer", help="Job search query"),
    location: str = typer.Option(None, help="Location filter"),
):
    """Only run the ingestion stage (fetch new jobs)."""
    from src.ingestion.orchestrator import IngestionOrchestrator
    from src.database import init_db

    async def _run():
        await init_db()
        orchestrator = IngestionOrchestrator()
        stats = await orchestrator.ingest_all(query, location)
        console.print(f"[green]✓ Ingestion complete:[/green] {stats}")

    asyncio.run(_run())


@app.command()
def review():
    """Show pending applications for review."""
    from src.review.review_queue import ReviewQueue

    async def _run():
        queue = ReviewQueue()
        pending = await queue.get_daily_queue()

        if not pending:
            console.print("[yellow]No applications pending review.[/yellow]")
            return

        from rich.table import Table

        table = Table(title="Pending Review")
        table.add_column("Company", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Score", style="green")
        table.add_column("Resume", style="dim")
        table.add_column("ID", style="dim")

        for item in pending:
            table.add_row(
                item["company"],
                item["title"],
                f"{item.get('fit_score', 0):.2f}",
                item["resume_path"],
                item["application_id"][:8],
            )

        console.print(table)

    asyncio.run(_run())


@app.command()
def approve(application_id: str = typer.Argument(help="Application ID to approve")):
    """Approve an application for submission."""
    from src.review.review_queue import ReviewQueue
    from uuid import UUID

    async def _run():
        queue = ReviewQueue()
        result = await queue.approve(UUID(application_id))
        console.print(f"[green]✓ {result['message']}[/green]")

    asyncio.run(_run())


@app.command()
def submit():
    """Submit all approved applications."""
    from src.pipeline import JobAgentPipeline

    async def _run():
        pipeline = JobAgentPipeline(user_profile_path="./data/user_profile.txt")
        await pipeline.submit_approved()

    asyncio.run(_run())


@app.command()
def stats():
    """Show application pipeline statistics."""
    from src.tracker.application_tracker import ApplicationTracker

    async def _run():
        tracker = ApplicationTracker()
        data = await tracker.get_stats()

        console.print(Panel.fit(
            f"[bold]Pipeline Statistics[/bold]\n\n"
            f"📊 Total Applications: {data['total_applications']}\n"
            f"⏳ Pending Review: {data['pending_review']}\n"
            f"✅ Submitted: {data['submitted']}\n"
            f"🎯 Interviews: {data['interviews']}\n"
            f"❌ Rejected: {data['rejected']}\n"
            f"🎉 Offers: {data['offers']}",
            border_style="green",
        ))

    asyncio.run(_run())


@app.command()
def init_template(
    output: str = typer.Option("./data/resume_template.docx", help="Output path for template"),
):
    """Create a resume template from user input (interactive)."""
    console.print("[bold]Let's create your resume template.[/bold]\n")

    user_data = {
        "name": typer.prompt("Full Name"),
        "email": typer.prompt("Email"),
        "phone": typer.prompt("Phone"),
        "linkedin": typer.prompt("LinkedIn URL"),
        "github": typer.prompt("GitHub URL", default=""),
        "location": typer.prompt("Location (city, country)"),
        "summary": typer.prompt("Professional Summary (2-3 sentences)"),
    }

    # Skills
    console.print("\n[cyan]Technical Skills (enter categories, empty to finish):[/cyan]")
    skills = {}
    while True:
        category = typer.prompt("Skill category (e.g., 'Languages', 'Frameworks')", default="")
        if not category:
            break
        skill_list = typer.prompt(f"Skills for '{category}' (comma-separated)")
        skills[category] = [s.strip() for s in skill_list.split(",")]
    user_data["skills"] = skills

    # Experience
    console.print("\n[cyan]Work Experience (enter companies, empty to finish):[/cyan]")
    experience = []
    while True:
        company = typer.prompt("Company name", default="")
        if not company:
            break
        exp = {
            "company": company,
            "title": typer.prompt("Job title"),
            "location": typer.prompt("Location"),
            "dates": typer.prompt("Date range (e.g., 'Jan 2022 - Present')"),
        }
        console.print("  Bullet points (empty to finish):")
        bullets = []
        while True:
            bullet = typer.prompt("  •", default="")
            if not bullet:
                break
            bullets.append(bullet)
        exp["bullets"] = bullets
        experience.append(exp)
    user_data["experience"] = experience

    # Education
    console.print("\n[cyan]Education:[/cyan]")
    education = []
    while True:
        institution = typer.prompt("Institution", default="")
        if not institution:
            break
        education.append({
            "institution": institution,
            "degree": typer.prompt("Degree"),
            "year": typer.prompt("Year"),
        })
    user_data["education"] = education

    # Create template
    from src.resume.formatter import ResumeFormatter

    formatter = ResumeFormatter.__new__(ResumeFormatter)
    formatter.create_default_template(output, user_data)
    console.print(f"\n[green]✓ Resume template created: {output}[/green]")


@app.command()
def check_emails():
    """Check for application status updates in Gmail."""
    from src.mcp.gmail_mcp import GmailMCP

    async def _run():
        gmail = GmailMCP()
        updates = await gmail.check_for_updates()
        if not updates:
            console.print("[yellow]No new status updates found.[/yellow]")
        else:
            for update in updates:
                console.print(
                    f"  📬 [{update['detected_status']}] {update['company']}: "
                    f"{update['subject']}"
                )

    asyncio.run(_run())


if __name__ == "__main__":
    app()
