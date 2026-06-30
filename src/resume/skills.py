"""Skills matching and keyword optimization utilities for resume tailoring."""


# MAANG/FAANG company identifiers
MAANG_COMPANIES = {
    "meta", "apple", "amazon", "netflix", "google", "alphabet",
    "microsoft", "nvidia", "tesla", "openai", "anthropic",
}

FAANG_COMPANIES = {"facebook", "meta", "apple", "amazon", "netflix", "google", "alphabet"}

# Top product-based companies
PRODUCT_COMPANIES = {
    "stripe", "airbnb", "uber", "lyft", "spotify", "twitter", "x",
    "salesforce", "adobe", "atlassian", "databricks", "snowflake",
    "datadog", "cloudflare", "figma", "notion", "vercel", "supabase",
    "coinbase", "robinhood", "plaid", "rippling", "ramp", "brex",
    "palantir", "anduril", "scale", "discord", "slack", "zoom",
    "shopify", "twilio", "square", "block", "doordash", "instacart",
    "pinterest", "snap", "reddit", "dropbox", "github", "gitlab",
    "hashicorp", "elastic", "mongodb", "confluent", "cockroach labs",
    "linear", "planetscale", "neon", "fly.io", "railway",
}

# Common tech skill synonyms for matching
SKILL_SYNONYMS = {
    "javascript": ["js", "javascript", "ecmascript"],
    "typescript": ["ts", "typescript"],
    "python": ["python", "python3"],
    "react": ["react", "reactjs", "react.js"],
    "node": ["node", "nodejs", "node.js"],
    "kubernetes": ["kubernetes", "k8s"],
    "docker": ["docker", "containerization"],
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "azure": ["azure", "microsoft azure"],
    "ci/cd": ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
    "postgresql": ["postgresql", "postgres"],
    "mongodb": ["mongodb", "mongo"],
    "graphql": ["graphql", "gql"],
    "rest": ["rest", "restful", "rest api"],
    "microservices": ["microservices", "micro-services"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "dl"],
    "natural language processing": ["nlp", "natural language processing"],
    "large language models": ["llm", "large language models"],
}


def is_target_company(company: str) -> bool:
    """Check if company is a target (MAANG/FAANG/Product-based)."""
    company_lower = company.lower().strip()
    return (
        company_lower in MAANG_COMPANIES
        or company_lower in FAANG_COMPANIES
        or company_lower in PRODUCT_COMPANIES
    )


def calculate_skill_overlap(candidate_skills: list[str], jd_skills: list[str]) -> dict:
    """Calculate overlap between candidate skills and JD requirements."""
    candidate_normalized = {_normalize_skill(s) for s in candidate_skills}
    jd_normalized = {_normalize_skill(s) for s in jd_skills}

    matched = candidate_normalized & jd_normalized
    missing = jd_normalized - candidate_normalized

    # Check synonyms for additional matches
    additional_matches = set()
    for jd_skill in missing:
        for canonical, synonyms in SKILL_SYNONYMS.items():
            if jd_skill in [s.lower() for s in synonyms]:
                # Check if candidate has any synonym
                for syn in synonyms:
                    if syn.lower() in candidate_normalized:
                        additional_matches.add(jd_skill)
                        break

    matched |= additional_matches
    missing -= additional_matches

    return {
        "matched": list(matched),
        "missing": list(missing),
        "match_ratio": len(matched) / len(jd_normalized) if jd_normalized else 0,
    }


def _normalize_skill(skill: str) -> str:
    """Normalize a skill name for comparison."""
    return skill.lower().strip().replace("-", "").replace("_", "").replace(".", "")
