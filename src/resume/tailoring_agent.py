"""Resume Tailoring Agent - The core engine that rewrites the resume template 
to match job description keywords while maintaining excellent formatting."""

import re
from pathlib import Path
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel

from src.config import settings
from src.parser.jd_parser import ParsedJobDescription
from src.scoring.fit_scorer import FitScore


class TailoredSection(BaseModel):
    """A tailored section of the resume."""

    section_name: str
    original_content: str
    tailored_content: str
    keywords_added: list[str]
    changes_made: list[str]


class TailoringResult(BaseModel):
    """Complete result of resume tailoring."""

    job_id: str
    company: str
    title: str
    sections_modified: list[TailoredSection]
    keywords_matched: list[str]
    keywords_added: list[str]
    ats_score_estimate: float
    output_path: str


TAILORING_SYSTEM_PROMPT = """You are an expert resume writer specializing in tech industry resumes 
for MAANG/FAANG and top product companies. Your job is to tailor a resume section to match a 
specific job description while:

1. MAINTAINING TRUTHFULNESS - Never fabricate experience or skills the candidate doesn't have
2. KEYWORD OPTIMIZATION - Naturally incorporate JD keywords into existing experience
3. IMPACT METRICS - Ensure bullet points have quantified achievements (%, $, scale numbers)
4. ACTION VERBS - Start bullets with strong action verbs matching the JD language
5. ATS OPTIMIZATION - Use exact terminology from the JD (e.g., "CI/CD" not "continuous integration")
6. BREVITY - Keep bullets concise (1-2 lines max), remove fluff
7. RELEVANCE - Prioritize experiences most relevant to this specific role

Rules:
- Only enhance/rephrase existing experiences, NEVER add fake ones
- Match the exact technology names used in the JD
- If the candidate has a skill mentioned in JD, make it MORE prominent
- Remove or de-emphasize irrelevant experiences for this role
- Maintain professional tone appropriate for the seniority level"""

TAILORING_USER_PROMPT = """Tailor this resume section for the following job:

TARGET JOB:
Company: {company}
Title: {title}
Key Skills Required: {skills_required}
Tech Stack: {tech_stack}
Seniority: {seniority_level}
Top Keywords: {keywords}

RESUME SECTION ({section_name}):
{section_content}

INSTRUCTIONS:
1. Rewrite this section to better match the job description
2. Naturally incorporate relevant keywords from the JD
3. Maintain truthfulness - only enhance wording, don't fabricate
4. Use metrics and quantified achievements where possible
5. Match the seniority level in tone and responsibility scope

Return JSON:
{{
    "tailored_content": "the rewritten section content",
    "keywords_added": ["list", "of", "keywords", "incorporated"],
    "changes_made": ["brief description of each change"]
}}"""

SUMMARY_TAILORING_PROMPT = """Write a professional summary/objective for this resume targeting:

Company: {company}
Role: {title}
Key Skills: {skills_required}
Seniority: {seniority_level}

Current summary: {current_summary}

Candidate's key strengths (from resume): {strengths}

Write a 2-3 sentence professional summary that:
1. Opens with years of experience and primary expertise
2. Highlights 2-3 skills most relevant to this specific role
3. Ends with the type of impact they can bring
4. Uses keywords from the JD naturally

Return JSON:
{{
    "tailored_content": "the professional summary",
    "keywords_added": ["list", "of", "keywords"],
    "changes_made": ["brief description of changes"]
}}"""


class ResumeTailoringAgent:
    """Tailors resume template against JD keywords with intelligent rewriting."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.template_path = Path(settings.resume_template_path)
        self.output_dir = Path(settings.resume_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def tailor_resume(
        self,
        job_id: str,
        company: str,
        title: str,
        parsed_jd: ParsedJobDescription,
        fit_score: FitScore,
        resume_sections: dict[str, str],
    ) -> TailoringResult:
        """Tailor the entire resume for a specific job."""
        sections_modified = []
        all_keywords_added = []

        # Tailor each section
        for section_name, section_content in resume_sections.items():
            if section_name.lower() in ("contact", "name", "education"):
                # Don't modify contact info or education (usually)
                continue

            if section_name.lower() in ("summary", "objective", "profile"):
                tailored = await self._tailor_summary(
                    company, title, parsed_jd, section_content, resume_sections
                )
            else:
                tailored = await self._tailor_section(
                    company, title, parsed_jd, section_name, section_content
                )

            sections_modified.append(tailored)
            all_keywords_added.extend(tailored.keywords_added)

        # Calculate ATS score estimate
        ats_score = self._estimate_ats_score(parsed_jd, all_keywords_added, resume_sections)

        # Generate output path
        safe_company = re.sub(r"[^\w\-]", "_", company)
        safe_title = re.sub(r"[^\w\-]", "_", title)[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_filename = f"{safe_company}_{safe_title}_{timestamp}.docx"
        output_path = str(self.output_dir / output_filename)

        return TailoringResult(
            job_id=job_id,
            company=company,
            title=title,
            sections_modified=sections_modified,
            keywords_matched=fit_score.matched_skills,
            keywords_added=list(set(all_keywords_added)),
            ats_score_estimate=ats_score,
            output_path=output_path,
        )

    async def _tailor_section(
        self,
        company: str,
        title: str,
        parsed_jd: ParsedJobDescription,
        section_name: str,
        section_content: str,
    ) -> TailoredSection:
        """Tailor a single resume section."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": TAILORING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": TAILORING_USER_PROMPT.format(
                        company=company,
                        title=title,
                        skills_required=", ".join(parsed_jd.skills_required),
                        tech_stack=", ".join(parsed_jd.tech_stack),
                        seniority_level=parsed_jd.seniority_level,
                        keywords=", ".join(parsed_jd.keywords),
                        section_name=section_name,
                        section_content=section_content,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        import json

        data = json.loads(content)

        return TailoredSection(
            section_name=section_name,
            original_content=section_content,
            tailored_content=data["tailored_content"],
            keywords_added=data.get("keywords_added", []),
            changes_made=data.get("changes_made", []),
        )

    async def _tailor_summary(
        self,
        company: str,
        title: str,
        parsed_jd: ParsedJobDescription,
        current_summary: str,
        all_sections: dict[str, str],
    ) -> TailoredSection:
        """Tailor the professional summary section."""
        # Extract strengths from other sections
        strengths = " | ".join(
            [v[:200] for k, v in all_sections.items() if k.lower() not in ("summary", "contact")]
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": TAILORING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SUMMARY_TAILORING_PROMPT.format(
                        company=company,
                        title=title,
                        skills_required=", ".join(parsed_jd.skills_required[:10]),
                        seniority_level=parsed_jd.seniority_level,
                        current_summary=current_summary,
                        strengths=strengths[:500],
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        import json

        data = json.loads(content)

        return TailoredSection(
            section_name="Summary",
            original_content=current_summary,
            tailored_content=data["tailored_content"],
            keywords_added=data.get("keywords_added", []),
            changes_made=data.get("changes_made", []),
        )

    def _estimate_ats_score(
        self,
        parsed_jd: ParsedJobDescription,
        keywords_added: list[str],
        resume_sections: dict[str, str],
    ) -> float:
        """Estimate ATS compatibility score."""
        all_resume_text = " ".join(resume_sections.values()).lower()
        all_keywords = set(parsed_jd.keywords + parsed_jd.skills_required + parsed_jd.tech_stack)

        if not all_keywords:
            return 0.5

        matched = sum(
            1 for kw in all_keywords if kw.lower() in all_resume_text
        )
        added = len(set(keywords_added))

        # Score based on keyword coverage
        coverage = (matched + added) / len(all_keywords)
        return min(coverage, 1.0)
