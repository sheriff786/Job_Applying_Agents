"""JD Parser - Extracts skills, level, location, tech stack from job descriptions using LLM."""

from openai import AsyncOpenAI
from pydantic import BaseModel

from src.config import settings


class ParsedJobDescription(BaseModel):
    """Structured output from JD parsing."""

    skills_required: list[str]
    skills_preferred: list[str]
    tech_stack: list[str]
    seniority_level: str  # junior, mid, senior, staff, principal
    years_experience_min: int | None
    years_experience_max: int | None
    location: str
    remote_policy: str  # remote, hybrid, onsite
    team_size: str | None
    company_stage: str | None  # startup, growth, enterprise
    education_required: str | None
    visa_sponsorship: bool | None
    key_responsibilities: list[str]
    keywords: list[str]  # Important keywords for resume tailoring


PARSE_SYSTEM_PROMPT = """You are an expert technical recruiter and job description analyst.
Extract structured information from the given job description.
Be thorough in identifying ALL technical skills, tools, frameworks, and technologies mentioned.
For keywords, extract the most important terms that a resume should contain to pass ATS screening.
Always classify the seniority level accurately based on context clues like:
- Years of experience required
- Leadership/mentorship mentions
- System design responsibilities
- "Senior", "Staff", "Principal" in title or body

Return valid JSON matching the schema exactly."""

PARSE_USER_PROMPT = """Parse this job description and extract structured data:

Company: {company}
Title: {title}

Description:
{description}

Return a JSON object with these fields:
- skills_required: list of required technical skills
- skills_preferred: list of nice-to-have skills
- tech_stack: list of specific technologies/frameworks/tools
- seniority_level: one of [junior, mid, senior, staff, principal]
- years_experience_min: minimum years (null if not stated)
- years_experience_max: maximum years (null if not stated)
- location: location string
- remote_policy: one of [remote, hybrid, onsite]
- team_size: team size if mentioned
- company_stage: one of [startup, growth, enterprise] or null
- education_required: degree requirement if mentioned
- visa_sponsorship: true/false/null
- key_responsibilities: top 5 responsibilities
- keywords: top 15 ATS keywords from the JD"""


class JDParser:
    """Parses job descriptions using LLM to extract structured data."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def parse(self, company: str, title: str, description: str) -> ParsedJobDescription:
        """Parse a job description into structured format."""
        # Strip HTML if present
        clean_description = self._strip_html(description)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": PARSE_USER_PROMPT.format(
                        company=company,
                        title=title,
                        description=clean_description[:8000],  # Token limit safety
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        return ParsedJobDescription.model_validate_json(content)

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from description."""
        from bs4 import BeautifulSoup

        if "<" in text and ">" in text:
            soup = BeautifulSoup(text, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        return text
