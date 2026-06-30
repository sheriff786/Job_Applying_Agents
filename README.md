# Job Applying Agent 🚀

An automated job application system targeting MAANG/FAANG and top product-based companies outside India. The agent ingests job listings, scores fit, tailors your resume per job description, and manages the full application lifecycle.

## Architecture

```
Job Sources (Greenhouse, Lever, RemoteOK, Wellfound, LinkedIn)
    │
    ▼
┌─────────────────────┐
│  Ingestion Agent    │ ← Scheduled fetch, dedup, normalize
└─────────────────────┘
    │
    ├──→ JD Parser (LLM) → Skills, level, location, stack
    │
    ├──→ Vector Store (pgvector) → JD + skill embeddings
    │
    ▼
┌─────────────────────┐
│  Fit Scoring Agent  │ ← Similarity + seniority/location rules
└─────────────────────┘
    │ (above threshold)
    ▼
┌─────────────────────┐     ┌──────────────┐
│ Resume Tailoring    │◄───►│  Drive MCP   │
│ Agent               │     │ Template+ver │
└─────────────────────┘     └──────────────┘
    │
    ▼
┌─────────────────────┐
│ Human Review Queue  │ ← Daily approve/edit before submission
└─────────────────────┘
    │
    ├──→ API Auto-submit (Greenhouse, Lever, Ashby)
    │
    ├──→ Manual Click-through (LinkedIn, other portals)
    │
    ▼
┌─────────────────────┐
│ Application Tracker │ ← Company, role, resume version, status
└─────────────────────┘
    │
    ├──→ Gmail MCP (detects status reply emails)
    │
    └──→ Calendar MCP (auto-creates interview holds)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- OpenAI API key

### Setup

1. **Clone and configure:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

2. **Start infrastructure:**
```bash
docker-compose up -d db redis
```

3. **Install dependencies:**
```bash
pip install -e ".[dev]"
```

4. **Initialize database:**
```bash
# DB tables are auto-created on first run
```

5. **Create your resume template:**
```bash
job-agent init-template
# Follow interactive prompts to create your base resume
```

6. **Edit your profile:**
```bash
# Edit data/user_profile.txt with your actual skills and preferences
```

### Usage

**Run full pipeline:**
```bash
job-agent run --query "senior software engineer" --location "remote"
```

**Just ingest new jobs:**
```bash
job-agent ingest --query "backend engineer"
```

**Review pending applications:**
```bash
job-agent review
```

**Approve and submit:**
```bash
job-agent approve <application-id>
job-agent submit
```

**Check email updates:**
```bash
job-agent check-emails
```

**View statistics:**
```bash
job-agent stats
```

### Run with Docker (full stack):
```bash
docker-compose up
```

### API Server
```bash
uvicorn src.api:app --reload
# API docs at http://localhost:8000/docs
```

## Configuration

### Target Filters (in `.env`)
- `TARGET_LOCATIONS`: US, UK, Canada, Germany, Netherlands, Singapore, Australia
- `EXCLUDED_LOCATIONS`: India
- `TARGET_COMPANIES_TYPE`: MAANG, FAANG, product-based
- `SENIORITY_LEVELS`: mid, senior, staff
- `FIT_SCORE_THRESHOLD`: 0.70 (minimum score to tailor resume)

### Resume Template
- Single DOCX template at `data/resume_template.docx`
- The agent tailors it per job without changing the base template
- Tailored versions saved in `data/generated_resumes/`

### Adding Company Boards
Edit `src/ingestion/orchestrator.py` to add more Greenhouse/Lever company slugs.

## Key Features

### Resume Tailoring Engine
- **ATS Optimization**: Matches exact keyword terminology from JD
- **Truthful Enhancement**: Only enhances existing experience, never fabricates
- **Metric-Driven**: Ensures quantified achievements in bullet points
- **Seniority-Aware**: Adjusts tone and responsibility scope
- **Multi-Section**: Tailors summary, experience, skills, and projects independently

### Fit Scoring
- 40% skill match weight
- 20% seniority match weight  
- 20% location match weight
- 20% company type weight
- Hard filter: Excludes India-based roles

### Smart Deduplication
- By external ID (same source)
- By company + title (cross-source)
- Content hash for edge cases

## Project Structure

```
src/
├── config.py              # Central settings from .env
├── database.py            # SQLAlchemy models (Jobs, Applications, ResumeVersions)
├── pipeline.py            # Main orchestrator
├── cli.py                 # Typer CLI interface
├── api.py                 # FastAPI web interface
├── tasks.py               # Celery scheduled tasks
├── ingestion/             # Job fetchers (Greenhouse, Lever, RemoteOK, etc.)
├── parser/                # JD Parser (LLM-based extraction)
├── vectorstore/           # pgvector embeddings
├── scoring/               # Fit scoring agent
├── resume/                # Resume tailoring + DOCX formatting
├── tracker/               # Application lifecycle tracking
├── review/                # Human review queue
├── submit/                # API auto-submit + manual instructions
└── mcp/                   # Gmail & Calendar integrations
```

## Scheduled Tasks (Celery)

| Task | Schedule | Description |
|------|----------|-------------|
| Ingest jobs | Every 6 hours | Fetch from all sources |
| Process pipeline | Every hour | Parse & score new jobs |
| Check emails | Every 2 hours | Gmail status detection |

## Security Notes

- API keys stored in `.env` (never committed)
- Google OAuth credentials in `credentials/` directory
- No auto-apply on LinkedIn (manual only, respects ToS)
- Human review required before any submission

## License

MIT
