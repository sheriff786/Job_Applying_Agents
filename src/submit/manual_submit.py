"""Manual click-through helper - Generates instructions for LinkedIn and other portals."""

from dataclasses import dataclass


@dataclass
class ManualSubmissionInstructions:
    """Instructions for manual submission on platforms that don't support API."""

    platform: str
    job_url: str
    resume_path: str
    steps: list[str]
    cover_letter: str | None = None
    notes: str | None = None


class ManualSubmitHelper:
    """Generates instructions for manual job applications.
    
    For platforms like LinkedIn that don't allow automated applications,
    this generates step-by-step instructions for the user.
    """

    def generate_instructions(
        self,
        platform: str,
        job_url: str,
        resume_path: str,
        company: str,
        title: str,
        cover_letter: str | None = None,
    ) -> ManualSubmissionInstructions:
        """Generate manual submission instructions."""
        if platform.lower() == "linkedin":
            return self._linkedin_instructions(job_url, resume_path, company, title, cover_letter)
        else:
            return self._generic_instructions(
                platform, job_url, resume_path, company, title, cover_letter
            )

    def _linkedin_instructions(
        self,
        job_url: str,
        resume_path: str,
        company: str,
        title: str,
        cover_letter: str | None,
    ) -> ManualSubmissionInstructions:
        """Generate LinkedIn-specific application instructions."""
        steps = [
            f"1. Open the job posting: {job_url}",
            "2. Click 'Easy Apply' or 'Apply' button",
            f"3. Upload your tailored resume from: {resume_path}",
            "4. Fill in any required fields (contact info should auto-fill)",
        ]
        if cover_letter:
            steps.append("5. Paste the cover letter in the additional info section")
        steps.append(f"{'6' if cover_letter else '5'}. Review all information and click Submit")
        steps.append(
            f"{'7' if cover_letter else '6'}. Mark as submitted in the tracker after completion"
        )

        return ManualSubmissionInstructions(
            platform="LinkedIn",
            job_url=job_url,
            resume_path=resume_path,
            steps=steps,
            cover_letter=cover_letter,
            notes=f"Application for {title} at {company}. Use the tailored resume version.",
        )

    def _generic_instructions(
        self,
        platform: str,
        job_url: str,
        resume_path: str,
        company: str,
        title: str,
        cover_letter: str | None,
    ) -> ManualSubmissionInstructions:
        """Generate generic portal application instructions."""
        steps = [
            f"1. Navigate to: {job_url}",
            "2. Click the Apply button",
            f"3. Upload resume from: {resume_path}",
            "4. Fill in required personal information",
            "5. Complete any additional screening questions",
        ]
        if cover_letter:
            steps.append("6. Add cover letter if field is available")
        steps.append(f"{'7' if cover_letter else '6'}. Submit and mark complete in tracker")

        return ManualSubmissionInstructions(
            platform=platform,
            job_url=job_url,
            resume_path=resume_path,
            steps=steps,
            cover_letter=cover_letter,
            notes=f"Application for {title} at {company}",
        )
