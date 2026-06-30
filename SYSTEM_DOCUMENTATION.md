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

**Target:** MAANG/FAANG and product-based companies **outside India**.

---

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                       JOB SOURCES                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │Greenhouse│  │  Lever   │  │ RemoteOK │  │ Wellfound  │  │
│  │  (API)   │  │  (API)   │  │  (API)   │  │ (Scraping) │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │              │          │
│  ┌────┴──────────────┴─────────────┴──────────────┴──────┐  │
│  │              LinkedIn (Manual Export)                  │  │
│  └───────────────────────┬───────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │    INGESTION AGENT     │
              │  • Fetch from sources  │
              │  • Deduplicate         │
              │  • Normalize schema    │
              │  • Filter out India    │
              └───────────┬────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
     ┌──────────────────┐  ┌───────────────────┐
     │   JD PARSER      │  │   VECTOR STORE    │
     │   (GPT-4o)       │  │   (pgvector)      │
     │                  │  │                   │
     │ Extracts:        │  │ Stores:           │
     │ • Skills         │  │ • JD embeddings   │
     │ • Seniority      │  │ • Skill vectors   │
     │ • Tech stack     │  │                   │
     │ • Location       │  │ Enables:          │
     │ • Keywords       │  │ • Similarity      │
     │ • Remote policy  │  │   search          │
     └────────┬─────────┘  └───────┬───────────┘
              │                    │
              └────────┬───────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │   FIT SCORING AGENT    │
          │                        │
          │ Weights:               │
          │ • 40% Skill match      │
          │ • 20% Seniority match  │
          │ • 20% Location match   │
          │ • 20% Company type     │
          │                        │
          │ Hard filter: India = 0 │
          │ Threshold: 0.70        │
          └───────────┬────────────┘
                      │
                      │ (score >= 0.70)
                      ▼
        ┌──────────────────────────┐      ┌──────────────┐
        │  RESUME TAILORING AGENT  │◄────►│  Google Drive │
        │                          │      │  (Template)   │
        │ For each section:        │      └──────────────┘
        │ • Summary → rewrite      │
        │ • Experience → optimize  │
        │ • Skills → reorder       │
        │ • Projects → highlight   │
        │                          │
        │ ATS keyword injection    │
        │ Truthfulness preserved   │
        └────────────┬─────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  RESUME FORMATTER    │
          │  (python-docx)       │
          │                      │
          │ • Reads DOCX template│
          │ • Writes tailored    │
          │   DOCX with perfect  │
          │   formatting         │
          │ • Calibri, borders,  │
          │   spacing, alignment │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  HUMAN REVIEW QUEUE  │
          │                      │
          │ Daily batch review:  │
          │ • View tailored PDF  │
          │ • See keyword diff   │
          │ • Approve / Reject   │
          │ • Edit if needed     │
          └──────────┬───────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
           ▼                   ▼
┌───────────────────┐ ┌──────────────────┐
│  API AUTO-SUBMIT  │ │ MANUAL CLICK-    │
│                   │ │ THROUGH          │
│ • Greenhouse API  │ │                  │
│ • Lever API       │ │ • LinkedIn       │
│ • Ashby API       │ │ • Other portals  │
│                   │ │ • Step-by-step   │
│ Automatic         │ │   instructions   │
└────────┬──────────┘ └────────┬─────────┘
         │                     │
         └──────────┬──────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  APPLICATION TRACKER  │
        │                       │
        │ Tracks:               │
        │ • Company + Role      │
        │ • Resume version used │
        │ • Application status  │
        │ • Submission method   │
        │ • Response received   │
        └───────────┬───────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
┌──────────────────┐ ┌─────────────────┐
│    GMAIL MCP     │ │  CALENDAR MCP   │
│                  │ │                 │
│ Detects:         │ │ Auto-creates:   │
│ • Rejections     │ │ • Interview     │
│ • Interview      │ │   events        │
│   invites        │ │ • Prep blocks   │
│ • Offers         │ │ • Reminders     │
│                  │ │                 │
│ Updates tracker  │ │ Extracts:       │
│ automatically    │ │ • Meeting links │
│                  │ │ • Date/time     │
└──────────────────┘ └─────────────────┘
```

---

## Component Deep Dive

### 1. Ingestion Agent

**Location:** `src/ingestion/`

**Purpose:** Fetches raw job listings from 5 different sources, normalizes them into a common schema, deduplicates, and stores in PostgreSQL.

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
| `orchestrator.py` | Coordinates all fetchers, runs dedup, stores results |

**Deduplication Strategy:**
1. **By external ID** — same job from same source won't be stored twice
2. **By company + title** — catches same job posted on multiple platforms
3. **Content hash** — SHA256 of `company|title|description[:200]` for edge cases

**Pre-configured company boards:**
- Greenhouse: Google, Meta, Netflix, Stripe, Airbnb, Databricks, Snowflake, Figma, Notion, Vercel, Coinbase, Robinhood, Plaid, Rippling, Ramp (20 companies)
- Lever: Netflix, Stripe, Figma, OpenAI, Anthropic, Databricks, Anduril, Scale (10 companies)

**Location filter:** Any job with "India" in location is dropped at ingestion time.

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

**Purpose:** The formatting engine that reads your DOCX template and writes beautifully formatted tailored versions.

**Design philosophy:** Your resume must look like a human crafted it — perfect alignment, consistent spacing, professional fonts, clean section separators.

**Formatting specifications:**

| Element | Specification |
|---------|--------------|
| **Font** | Calibri 10.5pt, color #333333 |
| **Name** | 18pt bold, centered, color #1A1A2E |
| **Contact** | 9pt, centered, gray (#555555), pipe-separated |
| **Section headers** | 11pt bold, color #1A1A2E, bottom border line |
| **Margins** | Top/Bottom: 1.5cm, Left/Right: 2.0cm |
| **Bullet points** | 0.5cm left indent, 2pt spacing after |
| **Experience title** | Bold title, normal company, tab-aligned date |

**How formatting works:**

```
Template DOCX
    │
    ▼ (deep copy — original never modified)
Copy of template
    │
    ▼ (identify sections by header detection)
    │   • Checks paragraph style (Heading styles)
    │   • Checks if all runs are bold + text < 40 chars
    │   • Checks against known header names
    │
    ▼ (replace content while preserving run formatting)
    │   • Keeps font, size, bold, color from original runs
    │   • Only changes the text content
    │
    ▼ (final formatting pass)
    │   • Ensures consistent bullet indentation
    │   • Cleans empty paragraphs
    │   • Validates spacing
    │
    ▼
Tailored DOCX saved to data/generated_resumes/
```

**Template creation:** `job-agent init-template` walks you through an interactive wizard that creates a professionally formatted base DOCX with all the right styles pre-configured.

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
```

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
