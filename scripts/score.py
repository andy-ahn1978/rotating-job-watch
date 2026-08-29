import re

# V6.1 profile-aware scoring
# Job Fit is intentionally separate from Company Fit.
# The goal is to rank industrial technical/commercial roles higher while
# keeping unrelated jobs at target companies low.

CORE_TITLE_TERMS = {
    "technical sales": 4.3,
    "sales engineer": 4.2,
    "technical sales representative": 4.5,
    "technical sales specialist": 4.4,
    "aftermarket sales": 4.5,
    "service sales": 4.3,
    "territory sales": 4.2,
    "territory manager": 4.1,
    "outside sales": 4.0,
    "retrofit specialist": 4.5,
    "product support sales": 4.3,
    "business development": 4.0,
    "sales manager": 4.0,
    "commercial manager": 3.9,
    "account manager": 3.8,
    "sales representative": 3.6,
    "sales specialist": 3.8,
}

ADJACENT_TITLE_TERMS = {
    "reliability engineer": 3.8,
    "reliability specialist": 3.8,
    "reliability analyst": 3.6,
    "condition monitoring": 3.7,
    "product support": 3.4,
    "technical support": 3.1,
    "technical project specialist": 2.7,
}

NON_SALES_TITLE = [
    "millwright", "journeyman", "mechanic", "maintenance technician",
    "vibration technician", "field technician", "service technician"
]

UNRELATED_TITLE = [
    "finance", "accounting", "human resources", "hr ", "software developer",
    "software engineer", "marketing coordinator", "warehouse", "driver",
    "customer service representative", "administrative", "payroll",
]

TECH = {
    "rotating equipment": 1.5,
    "compressor": 1.4,
    "reciprocating": 0.8,
    "pump": 1.2,
    "blower": 1.0,
    "fan": 0.7,
    "valve": 0.8,
    "condition monitoring": 1.2,
    "vibration": 0.7,
    "reliability": 0.9,
    "alignment": 0.6,
    "retrofit": 1.3,
    "upgrade": 0.7,
    "aftermarket": 1.3,
    "service sales": 1.0,
    "product support": 0.9,
    "field service": 0.6,
    "maintenance": 0.4,
    "hydraulic": 0.5,
    "mro": 0.6,
    "mechanical": 0.4,
    "fluid handling": 0.7,
    "equipment sales": 0.8,
}

INDUSTRY = {
    "refinery": 0.5,
    "petrochemical": 0.5,
    "oil and gas": 0.5,
    "power generation": 0.5,
    "mining": 0.5,
    "cement": 0.4,
    "steel": 0.4,
    "manufacturing": 0.4,
    "industrial": 0.4,
}

COMMERCIAL = {
    "key account": 0.7,
    "regional": 0.4,
    "territory": 0.4,
    "business development": 0.6,
    "customer relationship": 0.3,
    "customer relationships": 0.3,
    "prospecting": 0.4,
    "new business": 0.4,
    "quotation": 0.3,
    "proposal": 0.3,
    "contract": 0.2,
}

TITLE_PENALTIES = {
    "inside sales": -0.6,
    "coordinator": -0.5,
    "junior": -1.0,
    "entry level": -1.2,
}

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def _best_title_score(title):
    hits = []
    vals = []
    for term, value in CORE_TITLE_TERMS.items():
        if term in title:
            hits.append(term)
            vals.append(value)

    # Do not double-count overlapping title phrases. Use the strongest title signal,
    # with a small bonus when a second distinct commercial phrase is also present.
    if vals:
        base = max(vals)
        if len(set(hits)) > 1:
            base += min(0.5, 0.2 * (len(set(hits)) - 1))
        return base, hits

    adj_hits = []
    adj_vals = []
    for term, value in ADJACENT_TITLE_TERMS.items():
        if term in title:
            adj_hits.append(term)
            adj_vals.append(value)

    if adj_vals:
        return max(adj_vals), adj_hits

    return 0.0, []

def score_job(job, config=None):
    title = norm(job.get("title"))
    text = norm(" ".join([
        job.get("title", ""),
        job.get("description", ""),
        job.get("company", "")
    ]))

    title_score, title_hits = _best_title_score(title)

    # Keep obvious hands-on trade roles out unless the title also contains
    # a relevant commercial/technical-commercial signal.
    if any(k in title for k in NON_SALES_TITLE) and not title_hits:
        return 0.0, [], ["non-sales-title"], "excluded"

    # Explicitly unrelated office/professional functions at a target company
    # should not receive a high Job Fit merely because the company description
    # contains pumps, valves, compressors, etc.
    unrelated = any(k in title for k in UNRELATED_TITLE)

    score = title_score
    matched = list(title_hits)
    negatives = []

    # Technical/product relevance
    tech_added = 0.0
    for k, w in TECH.items():
        if k in text:
            tech_added += w
            matched.append(k)

    # Industry relevance
    industry_added = 0.0
    for k, w in INDUSTRY.items():
        if k in text:
            industry_added += w
            matched.append(k)

    # Commercial responsibility
    commercial_added = 0.0
    for k, w in COMMERCIAL.items():
        if k in text:
            commercial_added += w
            matched.append(k)

    if unrelated and title_score == 0:
        # Company boilerplate can still explain why the job was discovered,
        # but it should not make Finance/HR/etc. look like a career match.
        score = min(1.5, 0.3 * tech_added + 0.2 * industry_added)
    else:
        score += tech_added + industry_added + commercial_added

    # Target company is a small contextual bonus only. Company Fit remains separate.
    if job.get("target_company"):
        score += 0.7
        matched.append("target company")

    # Title-level penalties
    for k, p in TITLE_PENALTIES.items():
        if k in title:
            score += p
            negatives.append(k)

    # Generic role with no relevant title signal should stay low even if the
    # employer boilerplate contains relevant equipment words.
    if title_score == 0 and not any(k in title for k in ADJACENT_TITLE_TERMS):
        score = min(score, 4.0)

    score = max(0.0, min(10.0, round(score, 1)))
    category = "strong" if score >= 7.5 else ("match" if score >= 5.5 else "adjacent")

    return score, list(dict.fromkeys(matched)), negatives, category
