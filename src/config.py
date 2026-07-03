"""Central configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/job_agent"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/job_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Job Board APIs
    greenhouse_api_token: str = ""
    lever_api_key: str = ""
    ashby_api_key: str = ""

    # LinkedIn
    linkedin_export_dir: str = "./data/linkedin_exports"

    # Google Drive
    google_credentials_file: str = "./credentials/google_credentials.json"
    resume_template_drive_id: str = ""

    # Gmail & Calendar
    gmail_credentials_file: str = "./credentials/gmail_credentials.json"
    calendar_credentials_file: str = "./credentials/calendar_credentials.json"

    # Apify (for LinkedIn/Indeed scraping)
    apify_api_token: str = ""

    # Agent Configuration
    fit_score_threshold: float = 0.70
    target_locations: list[str] = [
        "India", "Germany", "Netherlands", "UK", "Ireland", "France", "Spain",
        "Switzerland", "Sweden", "Denmark", "Poland", "Austria",
        "Australia", "Japan", "Singapore", "Canada", "Remote",
    ]
    excluded_locations: list[str] = ["US", "USA", "United States"]
    target_companies_type: list[str] = ["MAANG", "FAANG", "product-based"]
    seniority_levels: list[str] = ["mid", "senior", "staff"]

    # Resume
    resume_template_path: str = "./data/resume_template.docx"
    resume_output_dir: str = "./data/generated_resumes"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
