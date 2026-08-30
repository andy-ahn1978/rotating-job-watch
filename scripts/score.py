import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# V6.5
# Final Job Fit =
#   (Offering Fit 5.0 * TF-IDF multiplier)
#   + Role Fit 2.0
#   + Responsibilities Fit 1.2
#   + Industry / Customer Fit 1.0
#   + Company Fit 0.8
#
# Offering = equipment + product + industrial technical service.
# TF-IDF only refines the 50% Offering component. It no longer reduces
# Role, Responsibilities, Industry, or Company Fit.

ROLE_TERMS = {
    "technical sales representative": 1.00,
    "technical sales specialist": 1.00,
    "technical sales": 1.00,
    "sales engineer": 1.00,
    "aftermarket sales": 1.00,
    "service sales": 0.98,
    "retrofit specialist": 1.00,
    "technical account manager": 0.98,
    "product support sales": 0.98,
    "territory sales": 0.96,
    "territory manager": 0.96,
    "outside sales": 0.94,
    "business development": 0.93,
    "account manager": 0.91,
    "regional sales": 0.91,
    "area sales": 0.91,
    "sales manager": 0.89,
    "sales specialist": 0.89,
    "sales representative": 0.86,
    "commercial manager": 0.86,
    "inside sales": 0.72,
}

OFFERING_DIRECT_EQUIPMENT = {
    "rotating equipment": 1.00,
    "rotating machinery": 1.00,
    "reciprocating compressor": 1.00,
    "centrifugal compressor": 0.98,
    "diaphragm compressor": 0.98,
    "compressor": 0.98,
    "compressed air": 0.96,
    "turbomachinery": 0.96,
    "compressor valve": 1.00,
    "compressor valves": 1.00,
    "packing ring": 0.98,
    "packing rings": 0.98,
    "rider ring": 1.00,
    "rider rings": 1.00,
    "packing case": 0.98,
    "packing cases": 0.98,
    "lubricator": 0.96,
    "lubrication system": 0.90,
    "blower": 0.92,
    "industrial fan": 0.90,
    "fan": 0.80,
}

OFFERING_STRONG_EQUIPMENT = {
    "vacuum pump": 0.90,
    "pump": 0.86,
    "pumps": 0.86,
    "mechanical seal": 0.88,
    "mechanical seals": 0.88,
    "condition monitoring": 0.88,
    "vibration analysis": 0.86,
    "vibration": 0.83,
    "predictive maintenance": 0.84,
    "reliability": 0.80,
    "alignment": 0.80,
    "bearing": 0.74,
    "bearings": 0.74,
    "wear ring": 0.78,
    "wear rings": 0.78,
    "valve": 0.72,
    "valves": 0.72,
    "ptfe": 0.62,
    "peek": 0.62,
}

OFFERING_ADJACENT_EQUIPMENT = {
    "fluid handling": 0.66,
    "process equipment": 0.65,
    "industrial machinery": 0.63,
    "industrial equipment": 0.62,
    "hydraulic": 0.58,
    "pneumatic": 0.58,
    "mro": 0.58,
}

# Services are offerings only when the job/company text also contains
# industrial/technical context. Generic "service" alone never qualifies.
OFFERING_DIRECT_SERVICE = {
    "aftermarket service": 0.98,
    "retrofit service": 0.98,
    "reliability service": 0.94,
    "condition monitoring": 0.92,
    "predictive maintenance": 0.90,
    "field service": 0.86,
    "maintenance service": 0.86,
    "industrial service": 0.84,
    "technical service": 0.84,
    "equipment service": 0.84,
    "inspection": 0.78,
    "diagnostic": 0.82,
    "emissions monitoring": 0.84,
    "environmental monitoring": 0.76,
}

SERVICE_CONTEXT = (
    "industrial", "equipment", "machinery", "mechanical", "plant",
    "manufacturing", "maintenance", "engineering", "technical",
    "compressor", "pump", "blower", "hydraulic", "pneumatic",
    "reliability", "emission", "emissions", "instrumentation",
    "refinery", "petrochemical", "power generation", "mining",
)

RESPONSIBILITY_TERMS = {
    "aftermarket": 1.00,
    "retrofit": 1.00,
    "field service": 0.95,
    "product support": 0.95,
    "root cause": 0.95,
    "failure analysis": 0.95,
    "troubleshooting": 0.92,
    "warranty": 0.90,
    "upgrade": 0.88,
    "site visit": 0.88,
    "customer site": 0.88,
    "distributor": 0.88,
    "commissioning": 0.85,
    "territory": 0.84,
    "technical support": 0.82,
    "channel": 0.80,
    "proposal": 0.80,
    "quotation": 0.80,
    "prospecting": 0.80,
    "new business": 0.80,
    "maintenance": 0.72,
}

INDUSTRY_TERMS = {
    "refinery": 1.00,
    "petrochemical": 1.00,
    "oil and gas": 0.98,
    "power generation": 0.98,
    "mining": 0.94,
    "steel": 0.90,
    "cement": 0.90,
    "pulp and paper": 0.90,
    "chemical": 0.88,
    "manufacturing": 0.78,
    "industrial": 0.72,
}

UNRELATED_TITLE = [
    "finance", "accounting", "human resources", "software developer",
    "software engineer", "data analyst", "warehouse", "driver",
    "customer service representative", "administrative", "payroll",
    "marketing coordinator",
]

NON_SALES_TITLE = [
    "millwright", "journeyman", "mechanic", "maintenance technician",
    "field technician", "service technician", "vibration technician",
]

TITLE_PENALTIES = {
    "junior": 1.0,
    "entry level": 1.2,
    "coordinator": 0.6,
}

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def build_job_text(job):
    return " ".join([
        job.get("title", ""),
        job.get("description", ""),
        job.get("company", ""),
        job.get("target_category", ""),
        " ".join(job.get("target_equipment", []) or []),
    ])

def build_tfidf_scores(jobs, profile):
    refs = [
        profile.get("career", ""),
        profile.get("target_roles", ""),
        profile.get("technical_domain", ""),
    ]
    job_docs = [build_job_text(job) for job in jobs]
    docs = refs + job_docs

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
    )
    matrix = vectorizer.fit_transform(docs)
    sims = cosine_similarity(matrix[3:], matrix[:3])

    results = []
    for row in sims:
        career_sim = float(row[0])
        role_sim = float(row[1])
        technical_sim = float(row[2])

        # Combined similarity is deliberately weighted toward technical/career
        # similarity because it is used only to refine Offering Fit.
        combined = (
            0.40 * career_sim +
            0.15 * role_sim +
            0.45 * technical_sim
        )
        results.append({
            "career": round(career_sim, 4),
            "role": round(role_sim, 4),
            "technical": round(technical_sim, 4),
            "combined": round(combined, 4),
        })
    return results

def best_match(text, table):
    hits = [(k, v) for k, v in table.items() if k in text]
    if not hits:
        return 0.0, []
    hits.sort(key=lambda x: x[1], reverse=True)
    best = hits[0][1]
    bonus = min(0.08, 0.02 * max(0, len(hits) - 1))
    return min(1.0, best + bonus), [k for k, _ in hits]

def offering_fit(text):
    direct, direct_hits = best_match(text, OFFERING_DIRECT_EQUIPMENT)
    strong, strong_hits = best_match(text, OFFERING_STRONG_EQUIPMENT)
    adjacent, adjacent_hits = best_match(text, OFFERING_ADJACENT_EQUIPMENT)

    service_context = any(term in text for term in SERVICE_CONTEXT)
    service, service_hits = best_match(text, OFFERING_DIRECT_SERVICE)
    if not service_context:
        service, service_hits = 0.0, []

    if direct > 0:
        value = min(1.0, direct + 0.05 * strong + 0.04 * service + 0.02 * adjacent)
        level = "direct"
    elif strong > 0:
        value = min(0.94, strong + 0.06 * service + 0.03 * adjacent)
        level = "strong"
    elif service > 0:
        # Industrial technical service is a legitimate offering in its own right.
        value = min(0.90, service + 0.03 * adjacent)
        level = "service"
    elif adjacent > 0:
        value = min(0.68, adjacent)
        level = "adjacent"
    else:
        value = 0.0
        level = "none"

    hits = list(dict.fromkeys(
        direct_hits + strong_hits + service_hits + adjacent_hits
    ))
    return value, hits, level

def role_fit(title):
    return best_match(title, ROLE_TERMS)

def responsibilities_fit(text):
    return best_match(text, RESPONSIBILITY_TERMS)

def industry_fit(text):
    return best_match(text, INDUSTRY_TERMS)

def company_fit(job):
    if not job.get("target_company"):
        return 0.0
    fit = job.get("target_fit")
    if not isinstance(fit, (int, float)):
        return 0.50
    return max(0.20, min(1.0, (fit - 7.0) / 3.0))

def tfidf_multiplier(sim, target_company=False, offering_level="none"):
    combined = float((sim or {}).get("combined", 0.0))

    if combined >= 0.12:
        multiplier = 1.00
    elif combined >= 0.09:
        multiplier = 0.95
    elif combined >= 0.06:
        multiplier = 0.90
    elif combined >= 0.04:
        multiplier = 0.85
    elif combined >= 0.02:
        multiplier = 0.75
    else:
        multiplier = 0.50

    # Protect known target-company offerings from sparse/truncated job text.
    if target_company and offering_level in ("direct", "strong", "service"):
        multiplier = max(multiplier, 0.80)

    return multiplier

def score_job(job, config=None):
    title = norm(job.get("title"))

    if any(term in title for term in UNRELATED_TITLE):
        return 0.5, [], ["unrelated-title"], "excluded"

    role_value, role_hits = role_fit(title)

    if any(term in title for term in NON_SALES_TITLE) and not role_hits:
        return 1.0, [], ["non-sales-title"], "excluded"

    text = norm(build_job_text(job))
    offering_value, offering_hits, offering_level = offering_fit(text)
    responsibility_value, responsibility_hits = responsibilities_fit(text)
    industry_value, industry_hits = industry_fit(text)
    company_value = company_fit(job)

    sim = job.get("_tfidf", {}) or {}
    multiplier = tfidf_multiplier(
        sim,
        target_company=bool(job.get("target_company")),
        offering_level=offering_level,
    )

    offering_raw = 5.0 * offering_value
    offering_adjusted = offering_raw * multiplier

    # Only Offering Fit is multiplied by TF-IDF.
    final_score = (
        offering_adjusted +
        2.0 * role_value +
        1.2 * responsibility_value +
        1.0 * industry_value +
        0.8 * company_value
    )

    negatives = []
    for term, penalty in TITLE_PENALTIES.items():
        if term in title:
            final_score -= penalty
            negatives.append(term)

    # Safety gates stay independent of TF-IDF.
    if offering_level == "none":
        final_score = min(final_score, 5.4)
    if role_value == 0:
        final_score = min(final_score, 5.4)

    final_score = round(max(0.0, min(10.0, final_score)), 1)

    matched = list(dict.fromkeys(
        role_hits + offering_hits + responsibility_hits + industry_hits
    ))
    matched += [
        f"Offering {offering_raw:.1f}/5",
        f"TF-IDF x{multiplier:.2f}",
        f"Offering adjusted {offering_adjusted:.1f}/5",
        f"TF-IDF career {sim.get('career', 0):.2f}",
        f"TF-IDF role {sim.get('role', 0):.2f}",
        f"TF-IDF technical {sim.get('technical', 0):.2f}",
    ]

    if job.get("target_company"):
        matched.append("target company")

    category = (
        "excellent" if final_score >= 9.0 else
        "strong" if final_score >= 8.0 else
        "good" if final_score >= 7.0 else
        "match" if final_score >= 6.0 else
        "adjacent"
    )

    return final_score, matched, negatives, category
