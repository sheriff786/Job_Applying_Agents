"""
Job Applying Agent — Streamlit Dashboard
=========================================
Run with: streamlit run dashboard.py
"""

import sys
from pathlib import Path

import streamlit as st
import requests
import pandas as pd

# ─── Config ───────────────────────────────────────────────────────────

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Job Agent Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar Navigation ──────────────────────────────────────────────

st.sidebar.title("🎯 Job Agent")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Search Jobs", "Applications", "Resumes", "Settings"],
    index=0,
)

# ─── Helper Functions ─────────────────────────────────────────────────


def api_get(endpoint: str):
    """GET request to the FastAPI backend."""
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        st.error("⚠️ Backend not running. Start it with: `uvicorn src.api:app --reload --port 8000`")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, data: dict):
    """POST request to the FastAPI backend."""
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        st.error("⚠️ Backend not running.")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

if page == "Dashboard":
    st.title("📊 Job Application Dashboard")
    st.markdown("---")

    # Health check
    health = api_get("/health")
    if health:
        components = health.get("components", {})
        col1, col2, col3 = st.columns(3)
        col1.metric("API Status", "✅ Online")
        openai_ok = components.get("openai", {}).get("status") == "configured"
        col2.metric("OpenAI", "✅ Connected" if openai_ok else "❌ Not Set")
        # Check if apify is in config or components
        apify_ok = "apify" in components or health.get("config", {}).get("apify_configured")
        col3.metric("Apify", "✅ Ready" if apify_ok else "⚠️ Optional")

    st.markdown("---")

    # Application Summary
    summary = api_get("/log/summary")
    if summary:
        st.subheader("Application Pipeline")

        total = summary.get("total", 0)
        if total == 0:
            st.info("No applications yet. Go to **Search Jobs** to get started!")
        else:
            cols = st.columns(5)
            cols[0].metric("Total", total)
            cols[1].metric("Pending Review", summary.get("pending_review", 0))
            cols[2].metric("Approved", summary.get("approved", 0))
            cols[3].metric("Submitted", summary.get("submitted", 0))
            cols[4].metric("Interview", summary.get("interview", 0))

            # Status breakdown chart
            import plotly.express as px

            status_data = {k: v for k, v in summary.items() if k != "total" and v > 0}
            if status_data:
                fig = px.pie(
                    values=list(status_data.values()),
                    names=list(status_data.keys()),
                    title="Applications by Status",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                st.plotly_chart(fig, use_container_width=True)

    # Recent applications
    log_data = api_get("/log/all")
    if log_data and log_data.get("applications"):
        st.subheader("Recent Applications")
        df = pd.DataFrame(log_data["applications"])
        st.dataframe(
            df.tail(10).iloc[::-1],  # Latest first
            use_container_width=True,
            hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════
# PAGE: SEARCH JOBS
# ═══════════════════════════════════════════════════════════════════════

elif page == "Search Jobs":
    st.title("🔍 Search & Score Jobs")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Score a Job", "Bulk Ingestion", "LinkedIn Search"])

    # --- Tab 1: Score a single job ---
    with tab1:
        st.subheader("Score a Job Posting")
        st.markdown("Paste a job description to see if it's a good fit.")

        with st.form("score_job_form"):
            company = st.text_input("Company", placeholder="e.g., Google")
            role = st.text_input("Role", placeholder="e.g., Senior Software Engineer")
            location = st.text_input("Location", placeholder="e.g., Bangalore, India")
            jd_text = st.text_area(
                "Job Description",
                height=300,
                placeholder="Paste the full job description here...",
            )
            submit_score = st.form_submit_button("🎯 Score This Job", type="primary")

        if submit_score and jd_text:
            with st.spinner("Analyzing with GPT-4o..."):
                result = api_post("/demo/score-job", {
                    "company": company,
                    "role": role,
                    "location": location,
                    "description": jd_text,
                })

            if result:
                score = result.get("fit_score", 0)
                rec = result.get("recommendation", "unknown")

                # Color-coded result
                if rec == "apply":
                    st.success(f"✅ **APPLY** — Fit Score: {score:.2f}")
                elif rec == "maybe":
                    st.warning(f"⚠️ **MAYBE** — Fit Score: {score:.2f}")
                else:
                    st.error(f"❌ **SKIP** — Fit Score: {score:.2f}")

                # Score breakdown
                breakdown = result.get("breakdown", {})
                if breakdown:
                    st.markdown("**Score Breakdown:**")
                    cols = st.columns(4)
                    cols[0].metric("Skills", f"{breakdown.get('skills_match', 0):.0%}")
                    cols[1].metric("Seniority", f"{breakdown.get('seniority_fit', 0):.0%}")
                    cols[2].metric("Location", f"{breakdown.get('location_fit', 0):.0%}")
                    cols[3].metric("Company", f"{breakdown.get('company_tier', 0):.0%}")

                reasoning = result.get("reasoning", "")
                if reasoning:
                    with st.expander("See reasoning"):
                        st.write(reasoning)

    # --- Tab 2: Bulk ingestion test ---
    with tab2:
        st.subheader("Test Job Ingestion")
        st.markdown("Fetch real job listings from company career pages.")

        if st.button("🚀 Run Ingestion Test", type="primary"):
            with st.spinner("Fetching jobs from Greenhouse/Lever APIs..."):
                result = api_get("/demo/ingestion-test")

            if result:
                jobs = result.get("sample_jobs", [])
                st.success(f"Found **{result.get('total_found', 0)}** jobs!")

                if jobs:
                    df = pd.DataFrame(jobs)
                    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Tab 3: LinkedIn search ---
    with tab3:
        st.subheader("LinkedIn Job Search (via Apify)")
        st.markdown("Search LinkedIn for jobs matching your profile.")

        with st.form("linkedin_search"):
            keywords = st.text_input("Keywords", value="Senior Software Engineer")
            search_location = st.text_input("Location", value="India")
            max_results = st.slider("Max Results", 5, 50, 20)
            submit_linkedin = st.form_submit_button("🔗 Search LinkedIn")

        if submit_linkedin:
            with st.spinner("Searching LinkedIn via Apify..."):
                result = api_post("/demo/linkedin-search", {
                    "keywords": keywords,
                    "location": search_location,
                    "max_results": max_results,
                })
            if result:
                st.success(f"Found {len(result.get('jobs', []))} jobs!")
                if result.get("jobs"):
                    df = pd.DataFrame(result["jobs"])
                    st.dataframe(df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# PAGE: APPLICATIONS
# ═══════════════════════════════════════════════════════════════════════

elif page == "Applications":
    st.title("📋 Application Tracker")
    st.markdown("---")

    log_data = api_get("/log/all")

    if not log_data or log_data.get("total", 0) == 0:
        st.info("No applications logged yet. Score some jobs and tailor resumes to get started!")
    else:
        # Filters
        col1, col2 = st.columns(2)
        applications = log_data["applications"]
        df = pd.DataFrame(applications)

        statuses = ["All"] + sorted(df["status"].unique().tolist()) if "status" in df.columns else ["All"]
        companies = ["All"] + sorted(df["company"].unique().tolist()) if "company" in df.columns else ["All"]

        with col1:
            filter_status = st.selectbox("Filter by Status", statuses)
        with col2:
            filter_company = st.selectbox("Filter by Company", companies)

        # Apply filters
        if filter_status != "All":
            df = df[df["status"] == filter_status]
        if filter_company != "All":
            df = df[df["company"] == filter_company]

        # Display
        st.markdown(f"**Showing {len(df)} applications**")
        st.dataframe(
            df.iloc[::-1],  # Latest first
            use_container_width=True,
            hide_index=True,
            column_config={
                "fit_score": st.column_config.ProgressColumn(
                    "Fit Score", min_value=0, max_value=1, format="%.2f"
                ),
                "url": st.column_config.LinkColumn("Job URL"),
                "resume_path": st.column_config.TextColumn("Resume File"),
            },
        )

        # Status update section
        st.markdown("---")
        st.subheader("Update Application Status")

        with st.form("update_status"):
            col1, col2, col3 = st.columns(3)
            with col1:
                upd_company = st.text_input("Company Name")
            with col2:
                upd_role = st.text_input("Role")
            with col3:
                new_status = st.selectbox(
                    "New Status",
                    ["pending_review", "approved", "submitted", "interview", "offer", "rejected"],
                )
            update_btn = st.form_submit_button("Update Status")

        if update_btn and upd_company and upd_role:
            # Update via CSV logger directly
            sys.path.insert(0, str(Path(__file__).parent))
            from src.tracker.csv_logger import ApplicationLogger
            logger = ApplicationLogger()
            logger.update_status(upd_company, upd_role, new_status)
            st.success(f"Updated {upd_company} - {upd_role} to **{new_status}**")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: RESUMES
# ═══════════════════════════════════════════════════════════════════════

elif page == "Resumes":
    st.title("📄 Generated Resumes")
    st.markdown("---")

    resumes_data = api_get("/log/resumes")

    if not resumes_data or resumes_data.get("total_resumes", 0) == 0:
        st.info("No tailored resumes generated yet.")
        st.markdown("""
        **How to generate resumes:**
        1. Go to **Search Jobs** → Score a job
        2. If it's a good fit, use the **Tailor Resume** endpoint
        3. The tailored DOCX appears here
        
        **Or use the API directly:**
        ```
        POST /demo/tailor-resume
        ```
        """)

        # Offer to create template
        st.markdown("---")
        st.subheader("Resume Template")

        template_path = Path("data/resume_template.docx")
        if template_path.exists():
            st.success(f"✅ Template exists: `{template_path}`")
            st.markdown("Open it in Word to customize before running the agent.")
        else:
            if st.button("📝 Create Default Template"):
                try:
                    from src.resume.formatter import create_default_template
                    create_default_template()
                    st.success("Template created! Open `data/resume_template.docx` in Word to fill in your details.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.metric("Total Tailored Resumes", resumes_data["total_resumes"])
        st.markdown(f"📁 Directory: `{resumes_data['directory']}`")
        st.markdown("---")

        # Resume table
        resumes = resumes_data["resumes"]
        df = pd.DataFrame(resumes)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "full_path": st.column_config.TextColumn("Open in Word (copy path)"),
                "size_kb": st.column_config.NumberColumn("Size (KB)", format="%.1f"),
            },
        )

        # Download section
        st.markdown("---")
        st.subheader("Quick Access")
        st.markdown("Click a resume below to open its folder:")

        for resume in resumes[:10]:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.text(resume["filename"])
            col2.text(resume["created"])
            col3.text(f"{resume['size_kb']} KB")

    # Tailor a new resume
    st.markdown("---")
    st.subheader("✨ Tailor New Resume")

    with st.form("tailor_resume"):
        company_t = st.text_input("Company", key="tailor_company")
        role_t = st.text_input("Role", key="tailor_role")
        jd_t = st.text_area("Job Description", height=200, key="tailor_jd")
        tailor_btn = st.form_submit_button("🪄 Tailor Resume", type="primary")

    if tailor_btn and jd_t:
        with st.spinner("Tailoring resume with GPT-4o... (this takes 10-20 seconds)"):
            result = api_post("/demo/tailor-resume", {
                "company": company_t,
                "role": role_t,
                "description": jd_t,
            })

        if result:
            if result.get("resume_path"):
                st.success(f"✅ Resume generated!")
                st.markdown(f"**File:** `{result['resume_path']}`")
                st.markdown("Open it in Word to review before submitting.")
            else:
                st.json(result)


# ═══════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════════════

elif page == "Settings":
    st.title("⚙️ Settings & Configuration")
    st.markdown("---")

    # System status
    st.subheader("System Status")
    health = api_get("/health")
    if health:
        st.json(health)
    else:
        st.warning("Cannot reach backend API")

    # Configuration display
    st.markdown("---")
    st.subheader("Current Configuration")

    env_path = Path(".env")
    if env_path.exists():
        st.success("✅ `.env` file found")
    else:
        st.warning("⚠️ No `.env` file. Create one with your API keys.")

    st.markdown("""
    **Required `.env` variables:**
    ```
    OPENAI_API_KEY=sk-...
    APIFY_API_TOKEN=apify_api_...
    ```
    
    **Optional:**
    ```
    GOOGLE_SHEET_ID=your-sheet-id
    GOOGLE_CREDENTIALS_FILE=credentials.json
    ```
    """)

    # Target locations
    st.markdown("---")
    st.subheader("Target Locations")
    st.markdown("""
    Currently targeting: **India, Germany, Netherlands, UK, Ireland, France, Spain, 
    Switzerland, Sweden, Denmark, Poland, Austria, Australia, Japan, Singapore, Canada, Remote**
    
    Excluding: **USA**
    
    To change: Edit `src/config.py` → `target_locations` and `excluded_locations`
    """)

    # Skills check
    st.markdown("---")
    st.subheader("Your Skills Profile")
    skills_data = api_get("/demo/skills-check")
    if skills_data:
        st.json(skills_data)

    # Quick actions
    st.markdown("---")
    st.subheader("Quick Actions")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh API Health"):
            st.rerun()
    with col2:
        if st.button("📂 Open Data Folder"):
            st.code("explorer data\\", language="powershell")


# ─── Footer ──────────────────────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Quick Links:**
    - [API Docs](http://127.0.0.1:8000/docs)
    - [API Health](http://127.0.0.1:8000/health)
    """
)
st.sidebar.markdown("---")
st.sidebar.caption("Job Applying Agent v0.1.0")
