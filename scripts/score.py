import re

# V6.3.2 Job Fit
# Weighting:
#   Equipment / Product Fit      50%
#   Target Role Fit              20%
#   Career Similarity (TF-IDF)   15%
#   Responsibilities Fit          7%
#   Industry / Customer Fit       5%
#   Company Fit influence         3%
#
# Total = 10.0 points

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
    "territory sales": 0.95,
    "territory manager": 0.95,
    "outside sales": 0.93,
    "business development": 0.92,
    "account manager": 0.90,
    "regional sales": 0.90,
    "area sales": 0.90,
    "sales manager": 0.88,
    "sales specialist": 0.88,
    "sales representative": 0.85,
    "commercial manager": 0.85,
    "inside sales": 0.70,
}

# Direct experience / closest product families.
EQUIPMENT_DIRECT = {
    "rotating equipment": 1.00,
    "rotating machinery": 1.00,
    "reciprocating compressor": 1.00,
    "centrifugal compressor": 0.98,
    "diaphragm compressor": 0.98,
    "compressor": 0.97,
    "compressed air": 0.95,
    "turbomachinery": 0.95,
    "compressor valve": 1.00,
    "compressor valves": 1.00,
    "packing ring": 0.98,
    "packing rings": 0.98,
    "rider ring": 1.00,
    "rider rings": 1.00,
    "packing case": 0.98,
    "packing cases": 0.98,
    "lubricator": 0.95,
    "lubrication system": 0.90,
    "blower": 0.90,
    "industrial fan": 0.88,
    "fan": 0.78,
}

# Strongly transferable rotating-equipment / reliability products.
EQUIPMENT_STRONG = {
    "pump": 0.82,
    "pumps": 0.82,
    "vacuum pump": 0.88,
    "mechanical seal": 0.86,
    "mechanical seals": 0.86,
    "condition monitoring": 0.86,
    "vibration": 0.82,
    "vibration analysis": 0.85,
    "predictive maintenance": 0.82,
    "reliability": 0.78,
    "alignment": 0.78,
    "bearing": 0.72,
    "bearings": 0.72,
    "valve": 0.68,
    "valves": 0.68,
    "wear ring": 0.75,
    "wear rings": 0.75,
    "ptfe": 0.60,
    "peek": 0.60,
}

# Adjacent industrial equipment; useful, but not enough for a high score alone.
EQUIPMENT_ADJACENT = {
    "hydraulic": 0.55,
    "pneumatic": 0.55,
    "mro": 0.55,
    "fluid handling": 0.62,
    "process equipment": 0.62,
    "industrial equipment": 0.58,
    "industrial machinery": 0.60,
}

RESPONSIBILITY_TERMS = {
    "aftermarket": 1.00,
    "retrofit": 1.00,
    "upgrade": 0.85,
    "field service": 0.90,
    "product support": 0.90,
    "technical support": 0.75,
    "troubleshooting": 0.88,
    "root cause": 0.90,
    "failure analysis": 0.90,
    "warranty": 0.85,
    "site visit": 0.85,
    "customer site": 0.85,
    "territory": 0.80,
    "distributor": 0.85,
    "channel": 0.75,
    "proposal": 0.75,
    "quotation": 0.75,
    "commissioning": 0.80,
    "maintenance": 0.65,
    "prospecting": 0.75,
    "new business": 0.75,
}

INDUSTRY_TERMS = {
    "refinery": 1.00,
    "petrochemical": 1.00,
    "oil and gas": 0.95,
    "power generation": 0.95,
    "mining": 0.90,
    "steel": 0.85,
    "cement": 0.85,
    "pulp and paper": 0.85,
    "chemical": 0.85,
    "manufacturing": 0.70,
    "industrial": 0.65,
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

def best_match(text, table):
    hits = [(k, v) for k, v in table.items() if k in text]
    if not hits:
        return 0.0, []
    # Strongest matching term determines the base. Additional distinct terms
    # add a small corroboration bonus without allowing keyword stuffing.
    hits.sort(key=lambda x: x[1], reverse=True)
    best = hits[0][1]
    bonus = min(0.08, 0.02 * max(0, len(hits) - 1))
    return min(1.0, best + bonus), [k for k, _ in hits]

def equipment_fit(text):
    direct, dh = best_match(text, EQUIPMENT_DIRECT)
    strong, sh = best_match(text, EQUIPMENT_STRONG)
    adjacent, ah = best_match(text, EQUIPMENT_ADJACENT)

    # Direct product experience dominates. Strong/adjacent matches can lift a
    # direct match slightly, but cannot overpower it.
    if direct > 0:
        value = min(1.0, direct + 0.08 * strong + 0.03 * adjacent)
    elif strong > 0:
        value = min(0.90, strong + 0.05 * adjacent)
    else:
        value = min(0.65, adjacent)

    return value, list(dict.fromkeys(dh + sh + ah))

def role_fit(title):
    return best_match(title, ROLE_TERMS)

def tfidf_fit(sim):
    # Short job ads vs long career profiles naturally produce low cosine values.
    # Calibrate each axis before combining.
    career = min(1.0, float(sim.get("career", 0.0)) / 0.08)
    role = min(1.0, float(sim.get("role", 0.0)) / 0.10)
    technical = min(1.0, float(sim.get("technical", 0.0)) / 0.10)
    return (0.50 * career) + (0.25 * role) + (0.25 * technical)

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
    # Convert Company Fit 8.0-10.0 into a 0-1 contribution.
    return max(0.20, min(1.0, (fit - 7.5) / 2.5))

def score_job(job, config=None):
    title = norm(job.get("title"))

    if any(k in title for k in UNRELATED_TITLE):
        return 0.5, [], ["unrelated-title"], "excluded"

    role_value, role_hits = role_fit(title)

    if any(k in title for k in NON_SALES_TITLE) and not role_hits:
        return 1.0, [], ["non-sales-title"], "excluded"

    text = norm(" ".join([
        job.get("title", ""),
        job.get("description", ""),
        job.get("company", ""),
        job.get("target_category", ""),
        " ".join(job.get("target_equipment", []) or []),
    ]))

    equipment_value, equipment_hits = equipment_fit(text)
    tfidf_value = tfidf_fit(job.get("_tfidf", {}) or {})
    responsibility_value, responsibility_hits = responsibilities_fit(text)
    industry_value, industry_hits = industry_fit(text)
    company_value = company_fit(job)

    # Weighted 10-point score.
    score = (
        5.0 * equipment_value +
        2.0 * role_value +
        1.5 * tfidf_value +
        0.7 * responsibility_value +
        0.5 * industry_value +
        0.3 * company_value
    )

    # Without a target commercial role, relevant equipment alone should not
    # create a high Job Fit.
    if role_value == 0:
        score = min(score, 5.4)

    negatives = []
    for term, penalty in TITLE_PENALTIES.items():
        if term in title:
            score -= penalty
            negatives.append(term)

    score = max(0.0, min(10.0, round(score, 1)))

    sim = job.get("_tfidf", {}) or {}
    matched = list(dict.fromkeys(
        role_hits + equipment_hits + responsibility_hits + industry_hits
    ))
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

    return score, matched, negatives, category
