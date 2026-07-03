"""Fit Scoring Agent - Evaluates how well a job matches the user's profile."""

from openai import AsyncOpenAI
from pydantic import BaseModel

from src.config import settings
from src.parser.jd_parser import ParsedJobDescription


class FitScore(BaseModel):
    """Result of fit scoring."""

    overall_score: float  # 0.0 to 1.0
    skill_match_score: float
    seniority_match_score: float
    location_match_score: float
    company_type_score: float
    reasoning: str
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation: str  # apply, maybe, skip


SCORING_SYSTEM_PROMPT = """You are a career advisor scoring job-candidate fit.
Given the candidate's profile and a parsed job description, evaluate the match.

Scoring rules:
1. Skill match (40% weight): How many required skills does the candidate have?
2. Seniority match (20% weight): Does the job level match candidate experience?
3. Location match (20% weight): Is the job in an acceptable location? Remote is always good.
4. Company type (20% weight): Prefer MAANG/FAANG and product-based companies.

Location rules:
- Target: India, Germany, Netherlands, UK, Europe, Australia, Japan, Singapore, Canada
- Exclude: USA/United States (hard filter - score 0)
- Remote roles get full location score

Return a JSON with exact fields as specified."""

SCORING_USER_PROMPT = """Score this job-candidate fit:

CANDIDATE PROFILE:
{user_profile}

JOB:
Company: {company}
Title: {title}
Skills Required: {skills_required}
Skills Preferred: {skills_preferred}
Tech Stack: {tech_stack}
Seniority: {seniority_level}
Location: {location}
Remote Policy: {remote_policy}

Return JSON with:
- overall_score: float 0-1
- skill_match_score: float 0-1
- seniority_match_score: float 0-1
- location_match_score: float 0-1
- company_type_score: float 0-1
- reasoning: brief explanation
- matched_skills: list of candidate skills matching JD
- missing_skills: list of required skills candidate lacks
- recommendation: "apply", "maybe", or "skip"
"""


class FitScoringAgent:
    """Scores job-candidate fit using LLM + rule-based filters."""

    def __init__(self, user_profile: str):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.user_profile = user_profile
        self.threshold = settings.fit_score_threshold

    async def score(
        self, company: str, title: str, parsed_jd: ParsedJobDescription
    ) -> FitScore:
        """Score a job against the user profile."""
        # Hard filters first
        if self._is_excluded_location(parsed_jd.location):
            return FitScore(
                overall_score=0.0,
                skill_match_score=0.0,
                seniority_match_score=0.0,
                location_match_score=0.0,
                company_type_score=0.0,
                reasoning="Job is in an excluded location (USA).",
                matched_skills=[],
                missing_skills=parsed_jd.skills_required,
                recommendation="skip",
            )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SCORING_USER_PROMPT.format(
                        user_profile=self.user_profile,
                        company=company,
                        title=title,
                        skills_required=", ".join(parsed_jd.skills_required),
                        skills_preferred=", ".join(parsed_jd.skills_preferred),
                        tech_stack=", ".join(parsed_jd.tech_stack),
                        seniority_level=parsed_jd.seniority_level,
                        location=parsed_jd.location,
                        remote_policy=parsed_jd.remote_policy,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        return FitScore.model_validate_json(content)

    def should_apply(self, score: FitScore) -> bool:
        """Determine if score is above threshold for application."""
        return score.overall_score >= self.threshold

    def _is_excluded_location(self, location: str) -> bool:
        """Hard filter for excluded locations."""
        if not location:
            return False
        location_lower = location.lower()
        for excluded in settings.excluded_locations:
            if excluded.lower() in location_lower:
                return True
        return False
