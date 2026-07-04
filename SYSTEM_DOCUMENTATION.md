# Job Applying Agent — Complete System Documentation

## Table of Contents

- [Job Applying Agent — Complete System Documentation](#job-applying-agent--complete-system-documentation)
  - [Table of Contents](#table-of-contents)
  - [System Overview](#system-overview)
  - [Architecture Flow](#architecture-flow)
  - [Component Deep Dive](#component-deep-dive)
    - [1. Ingestion Agent](#1-ingestion-agent)
    - [2. JD Parser (LLM)](#2-jd-parser-llm)
    - [3. Vector Store](#3-vector-store)
    - [4. Fit Scoring Agent](#4-fit-scoring-agent)
    - [5. Resume Tailoring Agent](#5-resume-tailoring-agent)
    - [6. Resume Formatter (DOCX Engine)](#6-resume-formatter-docx-engine)
    - [7. Human Review Queue](#7-human-review-queue)
    - [8. API Auto-Submit](#8-api-auto-submit)
    - [9. Manual Click-Through Helper](#9-manual-click-through-helper)
    - [10. Application Tracker](#10-application-tracker)
    - [11. Gmail MCP](#11-gmail-mcp)
    - [12. Calendar MCP](#12-calendar-mcp)
    - [13. Pipeline Orchestrator](#13-pipeline-orchestrator)
    - [14. Celery Scheduler](#14-celery-scheduler)
    - [15. CLI Interface](#15-cli-interface)
    - [16. FastAPI Server](#16-fastapi-server)
    - [17. Database Layer](#17-database-layer)
      - [`jobs`](#jobs)
      - [`applications`](#applications)
      - [`resume_versions`](#resume_versions)
  - [Data Flow Walkthrough](#data-flow-walkthrough)
  - [Configuration \& Environment](#configuration--environment)
  - [Infrastructure](#infrastructure)

---

## System Overview

The Job Applying Agent is a fully automated pipeline that:

1. **Finds** job openings from multiple sources (Greenhouse, Lever, RemoteOK, Wellfound, LinkedIn)
2. **Understands** each job description using GPT-4o (extracts skills, seniority, tech stack)
3. **Scores** how well each job matches your profile (skill overlap, location, company type)
4. **Tailors** your single resume template per job description (keyword optimization, ATS-friendly)
5. **Queues** tailored applications for your daily review (human-in-the-loop)
6. **Submits** approved applications via API or generates manual instructions
7. **Tracks** every application through its lifecycle (applied → interview → offer)
8. **Monitors** Gmail for status replies and auto-creates calendar holds for interviews

**Target:** Senior Data Scientist · AI/ML Engineer · Principal Data Scientist roles at MAANG/FAANG and product-based companies.

**Candidate Profile:** Mohammad Sheriff Mehmood — 6+ years experience in NLP, LLMs, GenAI, production MLOps. M.Tech from BITS Pilani.

---

## Architecture Flow

```mermaid
flowchart TB
    %% ─── TRIGGER ───
    trigger[/"🕐 Pipeline Trigger<br/><i>CLI / API / Scheduled</i>"/]
    
    %% ─── INGESTION LAYER ───
    subgraph ingestion["📥 JOB INGESTION"]
        direction LR
        gh["🏢 Greenhouse API<br/><i>Databricks · Anthropic<br/>Airbnb · Stripe · Figma<br/>Coinbase · Robinhood...</i>"]
        lever["🏢 Lever API<br/><i>Netflix · OpenAI<br/>Scale AI...</i>"]
        rok["🌐 RemoteOK<br/><i>Free API · remote<br/>engineering jobs</i>"]
        apify["🔗 Apify Scraper<br/><i>LinkedIn & Indeed<br/>via browser automation</i>"]
        linkedin["📋 LinkedIn Export<br/><i>Manual JSON/CSV<br/>exports from browser</i>"]
    end

    %% ─── ORCHESTRATOR ───
    orch["⚙️ Ingestion Orchestrator<br/><i>Deduplication · Normalization<br/>Location filtering · DB storage</i>"]

    %% ─── PARSING ───
    parser["🔍 JD Parser (GPT-4o)<br/><i>Extract: skills · tech stack<br/>seniority · keywords · requirements</i>"]

    %% ─── VECTOR STORE ───
    vectordb["🧠 Vector Store (pgvector)<br/><i>Generate embeddings<br/>Semantic similarity search</i>"]

    %% ─── SCORING ───
    scorer["📊 Fit Scoring Agent (GPT-4o)<br/><i>Score job vs user_profile.txt<br/>Skills match · Seniority · Location<br/>Threshold: 0.70+</i>"]

    %% ─── DECISION ───
    decision{{"🚦 Score ≥ 0.70?"}}

    %% ─── TAILORING ───
    tailor["✍️ Resume Tailoring Agent (GPT-4o)<br/><i>Rewrite summary · Add JD keywords<br/>Optimize for ATS · Keep truthful</i>"]

    %% ─── FORMATTER ───
    formatter["📄 Resume Formatter<br/><i>Build 2-page DOCX/PDF<br/>Exact template · Hyperlinks<br/>Consistent · formatting · ▸ bullets</i>"]

    %% ─── REVIEW ───
    review["👁️ Human Review Queue<br/><i>Daily review of tailored apps<br/>Approve / Reject / Edit</i>"]

    %% ─── SUBMISSION ───
    subgraph submit["📤 SUBMISSION"]
        direction LR
        api_submit["🤖 API Submit<br/><i>Greenhouse/Lever<br/>direct API apply</i>"]
        manual_submit["🖱️ Manual Submit Helper<br/><i>Open URL + pre-fill<br/>instructions for user</i>"]
    end

    %% ─── TRACKING ───
    tracker["📈 Application Tracker<br/><i>Status: applied → interview<br/>→ offer → rejected<br/>CSV + DB logging</i>"]

    %% ─── MCP INTEGRATIONS ───
    subgraph mcp["🔌 MCP INTEGRATIONS"]
        direction LR
        gmail["📧 Gmail MCP<br/><i>Monitor inbox for<br/>interview invites ·<br/>rejections · follow-ups</i>"]
        calendar["📅 Calendar MCP<br/><i>Auto-schedule interviews<br/>Block calendar slots<br/>Send reminders</i>"]
    end

    %% ─── OUTPUTS ───
    subgraph outputs["📁 OUTPUT FOLDERS"]
        direction LR
        actual["actual-resume/<br/><i>Original PDF<br/>(never modified)</i>"]
        generated["generated-resumes/<br/><i>Tailored DOCX + PDF<br/>per company/role</i>"]
        artifacts["artifacts/<br/><i>Scored results · found<br/>jobs · run logs</i>"]
    end

    %% ─── CONNECTIONS ───
    trigger --> ingestion
    gh & lever & rok & apify & linkedin --> orch
    orch --> parser
    parser --> vectordb
    vectordb --> scorer
    scorer --> decision
    decision -- "✅ Yes (Apply)" --> tailor
    decision -- "❌ No (Skip)" --> tracker
    tailor --> formatter
    formatter --> outputs
    formatter --> review
    review -- "✅ Approved" --> submit
    review -- "❌ Rejected" --> tracker
    api_submit & manual_submit --> tracker
    tracker --> mcp
    gmail --> tracker
    calendar --> tracker

    %% ─── STYLING ───
    classDef trigger fill:#FF6B6B,stroke:#333,color:#fff
    classDef ingestion fill:#4ECDC4,stroke:#333,color:#fff
    classDef process fill:#45B7D1,stroke:#333,color:#fff
    classDef ai fill:#96E6A1,stroke:#333,color:#000
    classDef decision fill:#FFE66D,stroke:#333,color:#000
    classDef output fill:#DDA0DD,stroke:#333,color:#000
    classDef mcp fill:#F7DC6F,stroke:#333,color:#000

    class trigger trigger
    class gh,lever,rok,apify,linkedin ingestion
    class orch,vectordb,formatter,review process
    class parser,scorer,tailor ai
    class decision decision
    class actual,generated,artifacts output
    class gmail,calendar,api_submit,manual_submit mcp
```

### Candidate Skill Set (Source of Truth)

| Category | Skills |
|----------|--------|
| **Languages** | Python (primary) — TensorFlow · PyTorch · Scikit-learn · NumPy · Pandas · OpenCV · YOLO · CNN |
| **GenAI & LLMs** | LangChain · LangSmith · OpenAI API · Gemini · RAG · LLMOps · Fine-tuning · Prompt Engineering · Agentic AI · MCP · Transformer Models · Sentence-Transformers · CrewAI · HuggingFace · DSPy · Multi-agent Systems · Text2SQL |
| **MLOps & Cloud** | MLflow · Docker · Kubernetes · Airflow · GCP (Vertex AI) · AWS (SageMaker · ECS · CodePipeline · Lambda · Comprehend · Textract) · Azure · Apache Spark · CI/CD |
| **Databases** | PostgreSQL · MongoDB · SQL · ChromaDB · FAISS · Pinecone |
| **Tools & Other** | Tableau · Weights & Biases · FastAPI · Flask · Django · A/B Testing · REST API Design · Git · React (for ML UIs) |

### Folder Structure

```
data/
  actual-resume/         → Original PDF (never modified)
  generated-resumes/     → Tailored DOCX + PDF per company/role
  artifacts/             → Scored results · found jobs · run timestamps
  user_profile.txt       → Candidate profile for fit scoring
  applications_log.csv   → CSV tracker
```

---

## Component Deep Dive

### 1. Ingestion Agent

**Location:** `src/ingestion/`

**Purpose:** Fetches raw job listings from 6 different sources, normalizes them into a common schema, deduplicates, and stores in PostgreSQL.

**How it works:**

```
Source APIs → RawJob objects → Deduplication → Job DB records
```

| File | Role |
|------|------|
| `base.py` | Defines `RawJob` dataclass and `BaseJobFetcher` abstract class |
| `greenhouse.py` | Fetches from Greenhouse boards API (`boards-api.greenhouse.io`) |
| `lever.py` | Fetches from Lever postings API (`api.lever.co`) |
| `remoteok.py` | Fetches from RemoteOK JSON API |
| `wellfound.py` | Scrapes Wellfound (ex-AngelList) using BeautifulSoup |
| `linkedin.py` | Parses manually exported LinkedIn job JSONs (no scraping) |
| `apify_scraper.py` | LinkedIn & Indeed scraping via Apify cloud actors |
| `orchestrator.py` | Coordinates all fetchers, runs dedup, stores results |

**Deduplication Strategy:**
1. **By external ID** — same job from same source won't be stored twice
2. **By company + title** — catches same job posted on multiple platforms
3. **Content hash** — SHA256 of `company|title|description[:200]` for edge cases

**Pre-configured company boards (verified working):**
- **Greenhouse:** Databricks (66 DS/ML jobs) · Airbnb (27) · Anthropic (49) · Stripe (21) · Figma (21) · Datadog (23) · Coinbase (9) · Robinhood (6) · Discord (2) · Twitch
- **Lever:** Netflix · OpenAI · Scale AI
- **Apify:** LinkedIn Jobs Scraper · Indeed Scraper (requires `APIFY_API_TOKEN`)

**Location filter:** Configurable via `EXCLUDED_LOCATIONS` in `.env`.

---

### 2. JD Parser (LLM)

**Location:** `src/parser/jd_parser.py`

**Purpose:** Takes raw job description text and extracts structured data using GPT-4o.

**How it works:**

```
Raw HTML/text description
    │
    ▼ (strip HTML via BeautifulSoup)
Clean text (max 8000 chars)
    │
    ▼ (GPT-4o with JSON mode)
ParsedJobDescription {
    skills_required: ["Python", "Kubernetes", ...]
    skills_preferred: ["Rust", "GraphQL", ...]
    tech_stack: ["React", "PostgreSQL", "AWS", ...]
    seniority_level: "senior"
    years_experience_min: 5
    years_experience_max: 8
    location: "San Francisco, CA"
    remote_policy: "hybrid"
    education_required: "BS in CS or equivalent"
    visa_sponsorship: true
    key_responsibilities: ["Design distributed systems", ...]
    keywords: ["microservices", "CI/CD", "system design", ...]  ← TOP 15 ATS keywords
}
```

**Key design decisions:**
- **Temperature 0.1** — near-deterministic output for consistency
- **JSON response format** — structured output, no parsing errors
- **8000 char limit** — stays within token limits even with long JDs
- **HTML stripping** — many ATS systems return HTML in descriptions
- **Keywords field** — explicitly extracts top 15 ATS keywords for resume tailoring

---

### 3. Vector Store

**Location:** `src/vectorstore/store.py`

**Purpose:** Stores job description embeddings in PostgreSQL using pgvector extension for fast similarity search.

**How it works:**

```
Job description + skills
    │
    ▼ (OpenAI text-embedding-3-small)
1536-dimensional vector
    │
    ▼ (stored in PostgreSQL via pgvector)
jobs.embedding_vec column (vector type)
    │
    ▼ (IVFFlat index for fast cosine similarity)
Find top-N similar jobs to user profile
```

**Operations:**
| Method | Purpose |
|--------|---------|
| `setup_pgvector()` | Creates extension + vector column + IVFFlat index |
| `generate_embedding()` | Calls OpenAI embedding API |
| `store_job_embedding()` | Combines description + skills, embeds, stores |
| `store_user_profile_embedding()` | Embeds user resume/profile |
| `find_similar_jobs()` | Cosine similarity search with min_score filter |
| `find_jobs_matching_skills()` | Embeds skill list and finds matching jobs |

**Why pgvector over Pinecone/Weaviate?**
- Self-hosted (no vendor lock-in)
- Lives in same PostgreSQL as other data (no extra infra)
- IVFFlat index handles thousands of jobs efficiently
- Free and open source

---

### 4. Fit Scoring Agent

**Location:** `src/scoring/fit_scorer.py`

**Purpose:** Evaluates how well each job matches your profile using a weighted scoring system + hard filters.

**Scoring formula:**

```
overall_score = (0.40 × skill_match)
              + (0.20 × seniority_match)
              + (0.20 × location_match)
              + (0.20 × company_type)
```

| Weight | Factor | How it's evaluated |
|--------|--------|-------------------|
| **40%** | Skill match | % of required skills you possess (including synonym matching) |
| **20%** | Seniority match | Does the role level match your experience? |
| **20%** | Location match | Is job in target location? Remote = full score |
| **20%** | Company type | MAANG/FAANG/Product company gets higher score |

**Hard filters (instant score = 0):**
- Job located in India → `skip`
- Job seniority doesn't match at all → heavily penalized

**Output:**
```python
FitScore {
    overall_score: 0.82,
    skill_match_score: 0.90,
    seniority_match_score: 0.80,
    location_match_score: 1.0,   # remote
    company_type_score: 0.95,    # MAANG
    reasoning: "Strong match. 9/10 required skills...",
    matched_skills: ["Python", "Kubernetes", "React", ...],
    missing_skills: ["Rust"],
    recommendation: "apply"      # apply | maybe | skip
}
```

**Threshold:** Only jobs scoring ≥ 0.70 proceed to resume tailoring (configurable via `FIT_SCORE_THRESHOLD`).

---

### 5. Resume Tailoring Agent

**Location:** `src/resume/tailoring_agent.py`

**Purpose:** The brain of the system. Takes your resume template and rewrites each section to match a specific job description's keywords — without fabricating experience.

**How it works:**

```
Your resume template (sections)
    +
Parsed JD (keywords, skills, seniority)
    +
Fit Score (matched/missing skills)
    │
    ▼ (GPT-4o per section, temperature 0.3)
    │
    ├─ Summary → Rewritten to highlight relevant skills
    ├─ Experience → Bullet points rephrased with JD keywords
    ├─ Skills → Reordered to match JD priority
    ├─ Projects → Highlighted relevant ones
    │
    ▼
TailoringResult {
    sections_modified: [TailoredSection, ...],
    keywords_matched: ["Python", "K8s", ...],
    keywords_added: ["distributed systems", "CI/CD", ...],
    ats_score_estimate: 0.85,
    output_path: "data/generated_resumes/Google_SeniorSWE_20260630.docx"
}
```

**Tailoring rules enforced via system prompt:**

| Rule | What it means |
|------|--------------|
| **Truthfulness** | NEVER adds fake experience or skills you don't have |
| **Keyword injection** | Uses EXACT terminology from JD (e.g., "CI/CD" not "continuous integration") |
| **Impact metrics** | Ensures bullet points have numbers (%, $, scale) |
| **Action verbs** | Starts bullets with strong verbs matching JD language |
| **Relevance ordering** | Most relevant experience first for this specific role |
| **Brevity** | Bullets stay 1-2 lines, no fluff |
| **Seniority tone** | Adjusts language based on role level |

**Sections that get modified:**
- ✅ Summary/Profile/Objective
- ✅ Experience/Work Experience
- ✅ Skills/Technical Skills
- ✅ Projects
- ❌ Contact info (never modified)
- ❌ Education (rarely modified)

**ATS Score Estimation:**
After tailoring, the agent calculates what percentage of JD keywords now appear in the resume. This gives a rough ATS compatibility estimate.

---

### 6. Resume Formatter (DOCX Engine)

**Location:** `src/resume/formatter.py`

**Purpose:** Builds ATS-optimized 2-page DOCX/PDF resumes from scratch following the exact original resume template.

**Design philosophy:** Resume must look like a human crafted it — exact template match, consistent formatting, clickable hyperlinks, ATS-parseable structure.

**Template structure (2 pages):**

```
PAGE 1:
├── Header (Name · Title · Contact with hyperlinks)
├── Professional Summary (with authentica PyPI link)
├── Technical Skills (consistent · separator)
├── Professional Experience
│   ├── ValueLabs · Hyderabad (Mar 2025 – Present)
│   │   └── 4 bullets with metrics (Businessolver embedded)
│   └── LTIMindtree · Pune (Jan 2024 – Mar 2025)
│       └── 5 bullets with metrics (GenAI/NLP)
│
PAGE 2:
├── Cognizant · Chennai (Dec 2019 – Jan 2024)
│   └── 4 bullets with metrics
├── Research Projects (3-5 with "View on GitHub →" links)
├── Education (BITS Pilani + OIST Bhopal)
└── Certifications & Awards
```

**Formatting specifications:**

| Element | Specification |
|---------|--------------|
| **Font** | Arial 9.5pt |
| **Name** | 16pt bold, centered |
| **Title** | 10.5pt, gray (#3C3C3C), centered |
| **Contact** | 9pt, centered, clickable hyperlinks (LinkedIn · GitHub · Portfolio) |
| **Section headers** | 10.5pt bold, black, bottom border (#333333) |
| **Margins** | Top/Bottom: 1.0cm, Left/Right: 1.5cm |
| **Bullet marker** | ▸ (triangle) with 0.4cm left indent |
| **Separator** | · (middle dot) consistently throughout |
| **Hyperlinks** | Blue (#0066CC), underlined (LinkedIn, GitHub, Portfolio, PyPI, project links) |
| **Page break** | Before Cognizant (ensures 2-page structure) |

**Hyperlinks embedded:**

| Text | URL |
|------|-----|
| LinkedIn | linkedin.com/in/mohammad-sheriff/ |
| github.com/sheriff786 | github.com/sheriff786 |
| Portfolio | sheriff786.github.io/My_Portfolio_Website/#about |
| authentica | pypi.org/project/authentica/ |
| View on GitHub → (per project) | github.com/sheriff786 |

**Key methods:**

| Method | Purpose |
|--------|---------|
| `read_sections()` | Returns resume text sections for tailoring agent |
| `write_tailored_resume(result)` | Builds DOCX from TailoringResult |
| `build_tailored_resume(company, title, ...)` | Direct DOCX build with extra keywords |
| `_add_hyperlink(paragraph, text, url)` | Adds clickable link via OxmlElement |
| `_add_bullet(doc, text)` | Adds ▸ formatted bullet |
| `_add_experience_entry(doc, exp)` | Company · Location → Title → Dates → Context → Bullets |

**Resume data source of truth:** `RESUME_DATA` dict in `formatter.py` contains all experience, projects, education, certifications extracted from the original PDF.

---

### 7. Human Review Queue

**Location:** `src/review/review_queue.py`

**Purpose:** Safety gate — no application is submitted without your approval.

**Workflow:**

```
Tailored resume ready
    │
    ▼
Added to review queue (status: pending_review)
    │
    ▼ (daily batch review via CLI or API)
    │
    ├─ APPROVE → Application moves to submission queue
    │
    ├─ REJECT → Application marked rejected, reason recorded
    │             Feedback loops back to improve scoring
    │
    └─ EDIT → Open DOCX, make manual changes, then approve
```

**What you see during review:**
- Company name and role title
- Fit score
- Resume file path (open in Word to inspect)
- ATS score estimate
- Keywords matched and added
- Sections that were modified

**CLI commands:**
```bash
job-agent review              # Show all pending
job-agent approve <id>        # Approve specific application
```

**API endpoints:**
```
GET  /review/pending          # List pending
POST /review/approve          # Approve
POST /review/reject           # Reject with reason
```

---

### 8. API Auto-Submit

**Location:** `src/submit/api_submit.py`

**Purpose:** Automatically submits approved applications to ATS platforms via their APIs.

**Supported platforms:**

| Platform | API Used | What it sends |
|----------|----------|--------------|
| **Greenhouse** | Candidate Ingestion API | Name, email, phone, LinkedIn, resume file |
| **Lever** | Postings Apply API | Name, email, phone, LinkedIn, GitHub, resume, cover letter |
| **Ashby** | Application Form Submit API | Name, email, phone, LinkedIn (JSON payload) |

**How it works:**

```
Approved application
    │
    ▼ (detect source platform from job record)
    │
    ├─ Greenhouse → POST multipart/form-data with resume file
    ├─ Lever → POST multipart/form-data with resume + cover letter
    └─ Ashby → POST JSON with field submissions
    │
    ▼ (on success)
    │
    Application status → "submitted"
    Tracker updated with submission method and timestamp
```

**Error handling:** If submission fails (rate limit, auth error, etc.), the error is logged and the application stays in "approved" status for retry.

---

### 9. Manual Click-Through Helper

**Location:** `src/submit/manual_submit.py`

**Purpose:** For platforms like LinkedIn that don't allow automated applications, generates step-by-step instructions.

**Example output for LinkedIn:**

```
📋 Manual Submit: Senior SWE at Google

1. Open the job posting: https://linkedin.com/jobs/view/123456
2. Click 'Easy Apply' or 'Apply' button
3. Upload your tailored resume from: data/generated_resumes/Google_SeniorSWE_20260630.docx
4. Fill in any required fields (contact info should auto-fill)
5. Paste the cover letter in the additional info section
6. Review all information and click Submit
7. Mark as submitted in the tracker after completion
```

**Why manual for LinkedIn?** LinkedIn's Terms of Service prohibit automated applications. We respect this — the agent prepares everything for you, you just click through.

---

### 10. Application Tracker

**Location:** `src/tracker/application_tracker.py`

**Purpose:** Central database for all applications with full lifecycle management.

**Status flow:**

```
pending_review → approved → submitted → ┬→ rejected
                                         ├→ interview → offer
                                         └→ (no response)
```

**What it tracks per application:**

| Field | Description |
|-------|------------|
| Job ID | Links to the job record |
| Resume version | Which tailored version was used |
| Resume path | File path to the DOCX |
| Cover letter | If generated |
| Status | Current lifecycle stage |
| Submitted at | Timestamp of submission |
| Submission method | api_greenhouse, api_lever, manual |
| Response received | Boolean — did company reply? |
| Response date | When the reply came |
| Notes | Free-form notes |

**Statistics dashboard:**
```bash
job-agent stats
```
```
📊 Pipeline Statistics

📊 Total Applications: 47
⏳ Pending Review: 5
✅ Submitted: 30
🎯 Interviews: 8
❌ Rejected: 12
🎉 Offers: 2
```

---

### 11. Gmail MCP

**Location:** `src/mcp/gmail_mcp.py`

**Purpose:** Monitors your Gmail inbox for application status updates and automatically classifies them.

**How it works:**

```
Gmail API (OAuth2)
    │
    ▼ (search for emails from recruiting domains)
    │   Query: "from:(greenhouse.io OR lever.co OR ashbyhq.com OR talent OR recruiting)"
    │
    ▼ (classify each email using regex patterns)
    │
    ├─ REJECTION patterns:
    │   "decided to move forward with other candidates"
    │   "unfortunately...not proceeding"
    │   "position has been filled"
    │
    ├─ INTERVIEW patterns:
    │   "schedule...interview"
    │   "like to speak with you"
    │   "next step/round/stage"
    │   "phone/video/onsite screen"
    │
    └─ OFFER patterns:
        "pleased to offer"
        "offer letter"
        "compensation package"
```

**Output per detected email:**
```python
{
    "email_id": "msg_abc123",
    "from": "recruiting@stripe.com",
    "subject": "Next Steps - Senior Engineer Role",
    "date": "2026-06-30",
    "detected_status": "interview",
    "company": "Stripe"
}
```

**What happens next:**
- Status is updated in the Application Tracker
- If interview detected → Calendar MCP creates a hold

---

### 12. Calendar MCP

**Location:** `src/mcp/calendar_mcp.py`

**Purpose:** Automatically creates Google Calendar events when interviews are detected.

**What it creates:**

```
Interview detected
    │
    ▼
┌──────────────────────────────────────────────┐
│ 🎯 Interview: Senior SWE @ Stripe (Phone)   │
│                                              │
│ Date: July 7, 2026 2:00 PM - 3:00 PM        │
│ Meeting Link: https://zoom.us/j/123456       │
│                                              │
│ --- PREP NOTES ---                           │
│ • Research Stripe recent news                │
│ • Review job description keywords            │
│ • Prepare STAR stories                       │
│ • Test meeting link 5 min before             │
│                                              │
│ Reminders: 1 day before, 1 hour, 15 min      │
│ Color: Red (important)                       │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│ 📝 Interview Prep: Stripe                    │
│ Date: July 7, 2026 1:00 PM - 2:00 PM        │
│ Color: Yellow                                │
└──────────────────────────────────────────────┘
```

**Smart extraction from emails:**
- **Date/time:** Regex patterns for common date formats in interview emails
- **Meeting links:** Detects Zoom, Google Meet, Microsoft Teams, Calendly URLs

---

### 13. Pipeline Orchestrator

**Location:** `src/pipeline.py`

**Purpose:** The main brain that coordinates all agents in sequence.

**Pipeline stages:**

```
Stage 1: Initialize
    │  • Create DB tables
    │  • Setup pgvector extension
    │
Stage 2: Ingest
    │  • Fetch from all 5 sources
    │  • Dedup and store
    │  • Filter out excluded locations
    │
Stage 3: Parse
    │  • GPT-4o extracts structured data from each JD
    │  • Generate and store embeddings
    │
Stage 4: Score
    │  • Score each parsed job against user profile
    │  • Apply weighted formula + hard filters
    │  • Log results with 🟢/🔴 indicators
    │
Stage 5: Tailor
    │  • For jobs scoring ≥ 0.70:
    │  • Read resume template sections
    │  • GPT-4o rewrites each section
    │  • Write formatted DOCX
    │  • Add to review queue
    │
Stage 6: Monitor
    │  • Check Gmail for status updates
    │  • Create calendar holds for interviews
    │
Stage 7: Summary
       • Print statistics table
       • Show pending review count
```

**Running the full pipeline:**
```bash
job-agent run --query "senior software engineer" --location "remote"
```

---

### 14. Celery Scheduler

**Location:** `src/tasks.py`

**Purpose:** Runs pipeline stages on autopilot at scheduled intervals.

**Schedule:**

| Task | Frequency | What it does |
|------|-----------|-------------|
| `ingest_jobs` | Every 6 hours | Fetches new jobs from all sources |
| `process_new_jobs` | Every 1 hour | Parses and scores newly ingested jobs |
| `check_email_updates` | Every 2 hours | Scans Gmail for status replies |

**Infrastructure:** Celery workers connect to Redis as the message broker. Celery Beat runs the scheduler.

**Running:**
```bash
# Worker (processes tasks)
celery -A src.tasks worker --loglevel=info

# Beat (schedules tasks)
celery -A src.tasks beat --loglevel=info
```

---

### 15. CLI Interface

**Location:** `src/cli.py`

**Purpose:** Command-line interface for all operations. Built with Typer + Rich for beautiful terminal output.

**Commands:**

| Command | What it does |
|---------|-------------|
| `job-agent run` | Run full pipeline (ingest → parse → score → tailor) |
| `job-agent ingest` | Only fetch new jobs |
| `job-agent review` | Show pending applications in a table |
| `job-agent approve <id>` | Approve application for submission |
| `job-agent submit` | Submit all approved applications |
| `job-agent stats` | Show pipeline statistics |
| `job-agent init-template` | Interactive resume template creator |
| `job-agent check-emails` | Check Gmail for status updates |

**Example output:**

```
╭──────────────────────────────╮
│ Job Applying Agent           │
│ Query: senior software eng   │
│ Location: remote             │
╰──────────────────────────────╯

📥 Stage 1: Ingesting jobs...
   Fetched: 234, New: 89, Duplicates: 145

🔍 Stage 2: Parsing job descriptions...
   ✓ Parsed: Stripe - Senior Backend Engineer
   ✓ Parsed: Airbnb - Staff Software Engineer
   ...

📊 Stage 3: Scoring fit...
   🟢 Stripe - Senior Backend Engineer: 0.88 (apply)
   🟢 Airbnb - Staff Software Engineer: 0.82 (apply)
   🔴 Random Corp - Junior Dev: 0.31 (skip)
   ...

✍️  Stage 4: Tailoring resumes...
   ✓ Tailored: Stripe - Senior Backend Engineer (ATS: 87%)
   ✓ Tailored: Airbnb - Staff Software Engineer (ATS: 82%)

📊 Pipeline Summary
┌────────────────────┬───────┐
│ Metric             │ Count │
├────────────────────┼───────┤
│ Total Applications │ 47    │
│ Pending Review     │ 5     │
│ Submitted          │ 30    │
│ Interviews         │ 8     │
│ Rejected           │ 12    │
│ Offers             │ 2     │
└────────────────────┴───────┘
```

---

### 16. FastAPI Server

**Location:** `src/api.py`

**Purpose:** REST API for programmatic access and future web dashboard integration.

**Endpoints:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/` | Health check |
| `GET` | `/stats` | Pipeline statistics |
| `GET` | `/review/pending` | List pending applications |
| `POST` | `/review/approve` | Approve application |
| `POST` | `/review/reject` | Reject with reason |
| `POST` | `/status/update` | Update application status |
| `GET` | `/applications/{company}` | Get applications by company |

**Running:**
```bash
uvicorn src.api:app --reload
# Docs at http://localhost:8000/docs (Swagger UI)
```

---

### 17. Database Layer

**Location:** `src/database.py`

**Purpose:** SQLAlchemy ORM models and async connection management.

**Tables:**

#### `jobs`
| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Primary key |
| source | String | greenhouse, lever, remoteok, etc. |
| external_id | String | Unique ID from source (for dedup) |
| company | String | Company name |
| title | String | Job title |
| description_raw | Text | Full job description |
| location | String | Job location |
| remote | Boolean | Is remote allowed? |
| seniority_level | String | junior/mid/senior/staff/principal |
| skills | String[] | Extracted skills array |
| tech_stack | String[] | Extracted technologies |
| parsed_data | JSONB | Full ParsedJobDescription as JSON |
| embedding_vec | vector(1536) | pgvector embedding |
| fit_score | Float | Calculated fit score |
| fit_reasoning | Text | Why this score |
| status | String | new → parsed → scored → tailored → applied |

#### `applications`
| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Primary key |
| job_id | UUID | Foreign key to jobs |
| resume_version | String | Version identifier |
| resume_path | Text | Path to tailored DOCX |
| cover_letter | Text | Generated cover letter |
| status | String | pending_review → approved → submitted → ... |
| submitted_at | DateTime | When submitted |
| submission_method | String | api or manual |
| response_received | Boolean | Did company reply? |

#### `resume_versions`
| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Primary key |
| job_id | UUID | Which job this was tailored for |
| file_path | Text | Path to DOCX file |
| changes_summary | Text | What was changed |
| keywords_matched | String[] | Keywords from JD found in resume |
| score_before | Float | ATS score before tailoring |
| score_after | Float | ATS score after tailoring |
| approved | Boolean | Was this version approved? |

---

## Data Flow Walkthrough

Here's a complete walkthrough of what happens when a job goes from discovery to application:

```
1. DISCOVER
   Greenhouse API returns: "Senior Software Engineer at Stripe"
   
2. NORMALIZE
   RawJob → Job record in PostgreSQL
   external_id: "gh_stripe_12345"
   status: "new"

3. PARSE
   GPT-4o extracts from description:
   skills_required: ["Python", "Go", "distributed systems"]
   tech_stack: ["Kubernetes", "gRPC", "PostgreSQL"]
   seniority: "senior"
   keywords: ["payment systems", "API design", "microservices", ...]
   status: "parsed"

4. EMBED
   text-embedding-3-small generates 1536-dim vector
   Stored in jobs.embedding_vec

5. SCORE
   skill_match: 0.90 (you have 9/10 skills)
   seniority_match: 0.85 (senior → senior, good match)
   location_match: 1.00 (remote role)
   company_type: 0.95 (Stripe = top product company)
   overall: 0.92 → recommendation: "apply"
   status: "scored"

6. TAILOR
   Summary: Rewritten to mention "payment systems" and "API design"
   Experience bullets: "microservices" and "gRPC" keywords injected
   Skills section: Python and Go moved to top
   ATS estimate: 87%
   Output: data/generated_resumes/Stripe_SeniorSWE_20260630_1430.docx
   status: "tailored"

7. QUEUE
   Application created with status: "pending_review"
   Shows up in `job-agent review`

8. APPROVE
   You run: `job-agent approve abc123`
   status: "approved"

9. SUBMIT
   Stripe uses Lever → API auto-submit
   Resume uploaded, form filled
   status: "submitted"

10. TRACK
    Gmail detects: "We'd love to schedule a phone screen"
    → status: "interview"
    → Calendar hold created for next week
    → Prep block created 1 hour before
```

---

## Configuration & Environment

All configuration lives in `.env`:

```bash
# LLM — powers parsing, scoring, and tailoring
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Database — stores jobs, applications, embeddings
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/job_agent

# Redis — Celery task queue broker
REDIS_URL=redis://localhost:6379/0

# Targeting rules
FIT_SCORE_THRESHOLD=0.70
TARGET_LOCATIONS=US,UK,Canada,Germany,Netherlands,Singapore,Australia
EXCLUDED_LOCATIONS=India
TARGET_COMPANIES_TYPE=MAANG,FAANG,product-based
SENIORITY_LEVELS=mid,senior,staff

# Resume paths
RESUME_TEMPLATE_PATH=./data/resume_template.docx
RESUME_OUTPUT_DIR=./data/generated_resumes
```flowchart TB
    %% ─── TRIGGER ───
    trigger[/"🕐 Pipeline Trigger<br/><i>CLI / API / Scheduled</i>"/]
    
    %% ─── INGESTION LAYER ───
    subgraph ingestion["📥 JOB INGESTION"]
        direction LR
        gh["🏢 Greenhouse API<br/><i>FAANG boards: Databricks,<br/>Anthropic, Airbnb, Stripe...</i>"]
        lever["🏢 Lever API<br/><i>Netflix, OpenAI,<br/>Scale AI...</i>"]
        rok["🌐 RemoteOK<br/><i>Free API, remote<br/>engineering jobs</i>"]
        apify["🔗 Apify Scraper<br/><i>LinkedIn & Indeed<br/>via browser automation</i>"]
        linkedin["📋 LinkedIn Export<br/><i>Manual JSON/CSV<br/>exports from browser</i>"]
    end

    %% ─── ORCHESTRATOR ───
    orch["⚙️ Ingestion Orchestrator<br/><i>Deduplication · Normalization<br/>Location filtering · DB storage</i>"]

    %% ─── PARSING ───
    parser["🔍 JD Parser (GPT-4o)<br/><i>Extract: skills, tech stack,<br/>seniority, keywords, requirements</i>"]

    %% ─── VECTOR STORE ───
    vectordb["🧠 Vector Store (pgvector)<br/><i>Generate embeddings<br/>Semantic similarity search</i>"]

    %% ─── SCORING ───
    scorer["📊 Fit Scoring Agent (GPT-4o)<br/><i>Score job vs user_profile.txt<br/>Skills match · Seniority · Location<br/>Threshold: 0.70+</i>"]

    %% ─── DECISION ───
    decision{{"🚦 Score ≥ 0.70?"}}

    %% ─── TAILORING ───
    tailor["✍️ Resume Tailoring Agent (GPT-4o)<br/><i>Rewrite summary · Add JD keywords<br/>Optimize for ATS · Keep truthful</i>"]

    %% ─── FORMATTER ───
    formatter["📄 Resume Formatter<br/><i>Build 2-page DOCX/PDF<br/>Exact template · Hyperlinks<br/>Consistent · formatting · ▸ bullets</i>"]

    %% ─── REVIEW ───
    review["👁️ Human Review Queue<br/><i>Daily review of tailored apps<br/>Approve / Reject / Edit</i>"]

    %% ─── SUBMISSION ───
    subgraph submit["📤 SUBMISSION"]
        direction LR
        api_submit["🤖 API Submit<br/><i>Greenhouse/Lever<br/>direct API apply</i>"]
        manual_submit["🖱️ Manual Submit Helper<br/><i>Open URL + pre-fill<br/>instructions for user</i>"]
    end

    %% ─── TRACKING ───
    tracker["📈 Application Tracker<br/><i>Status: applied → interview<br/>→ offer → rejected<br/>CSV + DB logging</i>"]

    %% ─── MCP INTEGRATIONS ───
    subgraph mcp["🔌 MCP INTEGRATIONS"]
        direction LR
        gmail["📧 Gmail MCP<br/><i>Monitor inbox for<br/>interview invites,<br/>rejections, follow-ups</i>"]
        calendar["📅 Calendar MCP<br/><i>Auto-schedule interviews<br/>Block calendar slots<br/>Send reminders</i>"]
    end

    %% ─── OUTPUTS ───
    subgraph outputs["📁 OUTPUT FOLDERS"]
        direction LR
        actual["actual-resume/<br/><i>Original PDF<br/>(never modified)</i>"]
        generated["generated-resumes/<br/><i>Tailored DOCX + PDF<br/>per company/role</i>"]
        artifacts["artifacts/<br/><i>Scored results, found<br/>jobs, run logs</i>"]
    end

    %% ─── CONNECTIONS ───
    trigger --> ingestion
    gh & lever & rok & apify & linkedin --> orch
    orch --> parser
    parser --> vectordb
    vectordb --> scorer
    scorer --> decision
    decision -- "✅ Yes (Apply)" --> tailor
    decision -- "❌ No (Skip)" --> tracker
    tailor --> formatter
    formatter --> outputs
    formatter --> review
    review -- "✅ Approved" --> submit
    review -- "❌ Rejected" --> tracker
    api_submit & manual_submit --> tracker
    tracker --> mcp
    gmail --> tracker
    calendar --> tracker

    %% ─── STYLING ───
    classDef trigger fill:#FF6B6B,stroke:#333,color:#fff
    classDef ingestion fill:#4ECDC4,stroke:#333,color:#fff
    classDef process fill:#45B7D1,stroke:#333,color:#fff
    classDef ai fill:#96E6A1,stroke:#333,color:#000
    classDef decision fill:#FFE66D,stroke:#333,color:#000
    classDef output fill:#DDA0DD,stroke:#333,color:#000
    classDef mcp fill:#F7DC6F,stroke:#333,color:#000

    class trigger trigger
    class gh,lever,rok,apify,linkedin ingestion
    class orch,vectordb,formatter,review process
    class parser,scorer,tailor ai
    class decision decision
    class actual,generated,artifacts output
    class gmail,calendar,api_submit,manual_submit mcp

---

## Infrastructure

**Docker Compose runs 4 services:**

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `db` | pgvector/pgvector:pg16 | 5432 | PostgreSQL + pgvector |
| `redis` | redis:7-alpine | 6379 | Celery message broker |
| `app` | Custom (Dockerfile) | 8000 | FastAPI + Pipeline |
| `worker` | Custom (Dockerfile) | — | Celery task worker |
| `beat` | Custom (Dockerfile) | — | Celery scheduler |

**Start everything:**
```bash
docker-compose up -d
```

**Start only infrastructure (for local development):**
```bash
docker-compose up -d db redis
```
flowchart TB
    %% ─── TRIGGER ───
    trigger[/"🕐 Pipeline Trigger<br/><i>CLI / API / Scheduled</i>"/]
    
    %% ─── INGESTION LAYER ───
    subgraph ingestion["📥 JOB INGESTION"]
        direction LR
        gh["🏢 Greenhouse API<br/><i>FAANG boards: Databricks,<br/>Anthropic, Airbnb, Stripe...</i>"]
        lever["🏢 Lever API<br/><i>Netflix, OpenAI,<br/>Scale AI...</i>"]
        rok["🌐 RemoteOK<br/><i>Free API, remote<br/>engineering jobs</i>"]
        apify["🔗 Apify Scraper<br/><i>LinkedIn & Indeed<br/>via browser automation</i>"]
        linkedin["📋 LinkedIn Export<br/><i>Manual JSON/CSV<br/>exports from browser</i>"]
    end

    %% ─── ORCHESTRATOR ───
    orch["⚙️ Ingestion Orchestrator<br/><i>Deduplication · Normalization<br/>Location filtering · DB storage</i>"]

    %% ─── PARSING ───
    parser["🔍 JD Parser (GPT-4o)<br/><i>Extract: skills, tech stack,<br/>seniority, keywords, requirements</i>"]

    %% ─── VECTOR STORE ───
    vectordb["🧠 Vector Store (pgvector)<br/><i>Generate embeddings<br/>Semantic similarity search</i>"]

    %% ─── SCORING ───
    scorer["📊 Fit Scoring Agent (GPT-4o)<br/><i>Score job vs user_profile.txt<br/>Skills match · Seniority · Location<br/>Threshold: 0.70+</i>"]

    %% ─── DECISION ───
    decision{{"🚦 Score ≥ 0.70?"}}

    %% ─── TAILORING ───
    tailor["✍️ Resume Tailoring Agent (GPT-4o)<br/><i>Rewrite summary · Add JD keywords<br/>Optimize for ATS · Keep truthful</i>"]

    %% ─── FORMATTER ───
    formatter["📄 Resume Formatter<br/><i>Build 2-page DOCX/PDF<br/>Exact template · Hyperlinks<br/>Consistent · formatting · ▸ bullets</i>"]

    %% ─── REVIEW ───
    review["👁️ Human Review Queue<br/><i>Daily review of tailored apps<br/>Approve / Reject / Edit</i>"]

    %% ─── SUBMISSION ───
    subgraph submit["📤 SUBMISSION"]
        direction LR
        api_submit["🤖 API Submit<br/><i>Greenhouse/Lever<br/>direct API apply</i>"]
        manual_submit["🖱️ Manual Submit Helper<br/><i>Open URL + pre-fill<br/>instructions for user</i>"]
    end

    %% ─── TRACKING ───
    tracker["📈 Application Tracker<br/><i>Status: applied → interview<br/>→ offer → rejected<br/>CSV + DB logging</i>"]

    %% ─── MCP INTEGRATIONS ───
    subgraph mcp["🔌 MCP INTEGRATIONS"]
        direction LR
        gmail["📧 Gmail MCP<br/><i>Monitor inbox for<br/>interview invites,<br/>rejections, follow-ups</i>"]
        calendar["📅 Calendar MCP<br/><i>Auto-schedule interviews<br/>Block calendar slots<br/>Send reminders</i>"]
    end

    %% ─── OUTPUTS ───
    subgraph outputs["📁 OUTPUT FOLDERS"]
        direction LR
        actual["actual-resume/<br/><i>Original PDF<br/>(never modified)</i>"]
        generated["generated-resumes/<br/><i>Tailored DOCX + PDF<br/>per company/role</i>"]
        artifacts["artifacts/<br/><i>Scored results, found<br/>jobs, run logs</i>"]
    end

    %% ─── CONNECTIONS ───
    trigger --> ingestion
    gh & lever & rok & apify & linkedin --> orch
    orch --> parser
    parser --> vectordb
    vectordb --> scorer
    scorer --> decision
    decision -- "✅ Yes (Apply)" --> tailor
    decision -- "❌ No (Skip)" --> tracker
    tailor --> formatter
    formatter --> outputs
    formatter --> review
    review -- "✅ Approved" --> submit
    review -- "❌ Rejected" --> tracker
    api_submit & manual_submit --> tracker
    tracker --> mcp
    gmail --> tracker
    calendar --> tracker

    %% ─── STYLING ───
    classDef trigger fill:#FF6B6B,stroke:#333,color:#fff
    classDef ingestion fill:#4ECDC4,stroke:#333,color:#fff
    classDef process fill:#45B7D1,stroke:#333,color:#fff
    classDef ai fill:#96E6A1,stroke:#333,color:#000
    classDef decision fill:#FFE66D,stroke:#333,color:#000
    classDef output fill:#DDA0DD,stroke:#333,color:#000
    classDef mcp fill:#F7DC6F,stroke:#333,color:#000

    class trigger trigger
    class gh,lever,rok,apify,linkedin ingestion
    class orch,vectordb,formatter,review process
    class parser,scorer,tailor ai
    class decision decision
    class actual,generated,artifacts output
    class gmail,calendar,api_submit,manual_submit mcpflowchart TB
    %% ─── TRIGGER ───
    trigger[/"🕐 Pipeline Trigger<br/><i>CLI / API / Scheduled</i>"/]
    
    %% ─── INGESTION LAYER ───
    subgraph ingestion["📥 JOB INGESTION"]
        direction LR
        gh["🏢 Greenhouse API<br/><i>FAANG boards: Databricks,<br/>Anthropic, Airbnb, Stripe...</i>"]
        lever["🏢 Lever API<br/><i>Netflix, OpenAI,<br/>Scale AI...</i>"]
        rok["🌐 RemoteOK<br/><i>Free API, remote<br/>engineering jobs</i>"]
        apify["🔗 Apify Scraper<br/><i>LinkedIn & Indeed<br/>via browser automation</i>"]
        linkedin["📋 LinkedIn Export<br/><i>Manual JSON/CSV<br/>exports from browser</i>"]
    end

    %% ─── ORCHESTRATOR ───
    orch["⚙️ Ingestion Orchestrator<br/><i>Deduplication · Normalization<br/>Location filtering · DB storage</i>"]

    %% ─── PARSING ───
    parser["🔍 JD Parser (GPT-4o)<br/><i>Extract: skills, tech stack,<br/>seniority, keywords, requirements</i>"]

    %% ─── VECTOR STORE ───
    vectordb["🧠 Vector Store (pgvector)<br/><i>Generate embeddings<br/>Semantic similarity search</i>"]

    %% ─── SCORING ───
    scorer["📊 Fit Scoring Agent (GPT-4o)<br/><i>Score job vs user_profile.txt<br/>Skills match · Seniority · Location<br/>Threshold: 0.70+</i>"]

    %% ─── DECISION ───
    decision{{"🚦 Score ≥ 0.70?"}}

    %% ─── TAILORING ───
    tailor["✍️ Resume Tailoring Agent (GPT-4o)<br/><i>Rewrite summary · Add JD keywords<br/>Optimize for ATS · Keep truthful</i>"]

    %% ─── FORMATTER ───
    formatter["📄 Resume Formatter<br/><i>Build 2-page DOCX/PDF<br/>Exact template · Hyperlinks<br/>Consistent · formatting · ▸ bullets</i>"]

    %% ─── REVIEW ───
    review["👁️ Human Review Queue<br/><i>Daily review of tailored apps<br/>Approve / Reject / Edit</i>"]

    %% ─── SUBMISSION ───
    subgraph submit["📤 SUBMISSION"]
        direction LR
        api_submit["🤖 API Submit<br/><i>Greenhouse/Lever<br/>direct API apply</i>"]
        manual_submit["🖱️ Manual Submit Helper<br/><i>Open URL + pre-fill<br/>instructions for user</i>"]
    end

    %% ─── TRACKING ───
    tracker["📈 Application Tracker<br/><i>Status: applied → interview<br/>→ offer → rejected<br/>CSV + DB logging</i>"]

    %% ─── MCP INTEGRATIONS ───
    subgraph mcp["🔌 MCP INTEGRATIONS"]
        direction LR
        gmail["📧 Gmail MCP<br/><i>Monitor inbox for<br/>interview invites,<br/>rejections, follow-ups</i>"]
        calendar["📅 Calendar MCP<br/><i>Auto-schedule interviews<br/>Block calendar slots<br/>Send reminders</i>"]
    end

    %% ─── OUTPUTS ───
    subgraph outputs["📁 OUTPUT FOLDERS"]
        direction LR
        actual["actual-resume/<br/><i>Original PDF<br/>(never modified)</i>"]
        generated["generated-resumes/<br/><i>Tailored DOCX + PDF<br/>per company/role</i>"]
        artifacts["artifacts/<br/><i>Scored results, found<br/>jobs, run logs</i>"]
    end

    %% ─── CONNECTIONS ───
    trigger --> ingestion
    gh & lever & rok & apify & linkedin --> orch
    orch --> parser
    parser --> vectordb
    vectordb --> scorer
    scorer --> decision
    decision -- "✅ Yes (Apply)" --> tailor
    decision -- "❌ No (Skip)" --> tracker
    tailor --> formatter
    formatter --> outputs
    formatter --> review
    review -- "✅ Approved" --> submit
    review -- "❌ Rejected" --> tracker
    api_submit & manual_submit --> tracker
    tracker --> mcp
    gmail --> tracker
    calendar --> tracker

    %% ─── STYLING ───
    classDef trigger fill:#FF6B6B,stroke:#333,color:#fff
    classDef ingestion fill:#4ECDC4,stroke:#333,color:#fff
    classDef process fill:#45B7D1,stroke:#333,color:#fff
    classDef ai fill:#96E6A1,stroke:#333,color:#000
    classDef decision fill:#FFE66D,stroke:#333,color:#000
    classDef output fill:#DDA0DD,stroke:#333,color:#000
    classDef mcp fill:#F7DC6F,stroke:#333,color:#000

    class trigger trigger
    class gh,lever,rok,apify,linkedin ingestion
    class orch,vectordb,formatter,review process
    class parser,scorer,tailor ai
    class decision decision
    class actual,generated,artifacts output
    class gmail,calendar,api_submit,manual_submit mcp