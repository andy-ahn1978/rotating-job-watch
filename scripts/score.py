import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROLE_TERMS = [
    "technical sales", "sales engineer", "aftermarket sales", "service sales",
    "territory sales", "territory manager", "outside sales", "account manager",
    "technical account manager", "business development", "sales manager",
    "regional sales", "area sales", "product support", "retrofit specialist",
    "sales representative", "sales specialist", "commercial manager",
]

UNRELATED_TITLE = [
    "finance", "accounting", "human resources", "software developer",
    "software engineer", "data analyst", "warehouse", "driver",
    "customer service representative", "administrative", "payroll",
]

NON_SALES_TITLE = [
    "millwright", "journeyman", "mechanic", "maintenance technician",
    "field technician", "service technician", "vibration technician",
]

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def build_job_text(job):
    parts = [
        job.get("title", ""),
        job.get("description", ""),
        job.get("company", ""),
        job.get("target_category", ""),
        " ".join(job.get("target_equipment", []) or []),
    ]
    return " ".join(str(x) for x in parts if x)

def build_tfidf_scores(jobs, profile):
    refs = [
        profile.get("career", ""),
        profile.get("target_roles", ""),
        profile.get("technical_domain", ""),
    ]
    job_docs = [build_job_text(j) for j in jobs]
    docs = refs + job_docs

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
    )
    matrix = vectorizer.fit_transform(docs)

    ref_matrix = matrix[:3]
    job_matrix = matrix[3:]
    sims = cosine_similarity(job_matrix, ref_matrix)

    results = []
    for row in sims:
        career_sim = float(row[0])
        role_sim = float(row[1])
        tech_sim = float(row[2])

        # Weighted semantic similarity. Career is primary, then target role,
        # then technical domain.
        combined = (0.50 * career_sim) + (0.30 * role_sim) + (0.20 * tech_sim)
        results.append({
            "career": round(career_sim, 4),
            "role": round(role_sim, 4),
            "technical": round(tech_sim, 4),
            "combined": round(combined, 4),
        })
    return results

def _role_signal(title):
    title = norm(title)
    hits = [term for term in ROLE_TERMS if term in title]
    if not hits:
        return 0.0, []
    # Keep role contribution modest; TF-IDF does most of the scoring.
    if any(x in title for x in [
        "technical sales", "sales engineer", "aftermarket sales",
        "service sales", "retrofit specialist", "technical account manager"
    ]):
        return 2.2, hits
    if any(x in title for x in [
        "territory", "outside sales", "account manager",
        "business development", "regional sales", "area sales"
    ]):
        return 1.9, hits
    return 1.6, hits

def score_job(job, config=None):
    title = norm(job.get("title"))
    role_bonus, role_hits = _role_signal(title)

    # Keep obviously unrelated functions at relevant companies from being
    # inflated by company/equipment metadata.
    if any(k in title for k in UNRELATED_TITLE):
        return 0.5, role_hits, ["unrelated-title"], "excluded"

    if any(k in title for k in NON_SALES_TITLE) and not role_hits:
        return 1.0, role_hits, ["non-sales-title"], "excluded"

    sim = job.get("_tfidf", {}) or {}
    combined = float(sim.get("combined", 0.0))

    # Calibrated semantic component:
    # ~0.10 similarity => ~3.2 points
    # ~0.20 similarity => ~5.2 points
    # ~0.30 similarity => ~6.5 points
    # ~0.40+ similarity => ~7.2 points
    semantic = min(7.2, 22.0 * combined)

    target_bonus = 0.0
    if job.get("target_company"):
        fit = job.get("target_fit")
        if isinstance(fit, (int, float)):
            target_bonus = max(0.3, min(0.8, (fit - 7.5) * 0.32))
        else:
            target_bonus = 0.4

    score = semantic + role_bonus + target_bonus

    # A role with no commercial/target-role title signal should not become a
    # strong match only because the employer sells relevant equipment.
    if not role_hits:
        score = min(score, 5.4)

    score = max(0.0, min(10.0, round(score, 1)))

    matched = list(dict.fromkeys(role_hits))
    matched += [
        f"TF-IDF career {sim.get('career', 0):.2f}",
        f"TF-IDF role {sim.get('role', 0):.2f}",
        f"TF-IDF technical {sim.get('technical', 0):.2f}",
    ]
    if job.get("target_company"):
        matched.append("target company")

    category = (
        "excellent" if score >= 9.0 else
        "strong" if score >= 8.0 else
        "good" if score >= 7.0 else
        "match" if score >= 6.0 else
        "adjacent"
    )
    return score, matched, [], category
