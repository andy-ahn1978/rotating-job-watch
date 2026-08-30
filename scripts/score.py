import re

PRIMARY_SALES_TITLE = {
    "technical sales": 4.0, "sales engineer": 4.0, "aftermarket sales": 4.0,
    "product support sales": 4.0, "retrofit specialist": 4.0,
    "technical account manager": 4.0, "territory sales": 3.8,
    "territory manager": 3.8, "outside sales": 3.8,
    "business development": 3.7, "account manager": 3.6,
    "key account manager": 3.6, "regional sales": 3.6,
    "area sales": 3.6, "sales manager": 3.5, "sales specialist": 3.5,
    "sales representative": 3.4, "commercial manager": 3.3,
    "inside sales": 2.8, "sales coordinator": 2.5,
}

EQUIPMENT = {
    "rotating equipment": 3.5, "rotating machinery": 3.5,
    "reciprocating compressor": 3.5, "centrifugal compressor": 3.4,
    "diaphragm compressor": 3.4, "compressor": 3.2,
    "compressed air": 3.0, "turbomachinery": 3.2,
    "blower": 2.8, "vacuum pump": 2.8, "pump": 2.7,
    "mechanical seal": 2.7, "condition monitoring": 2.7,
    "vibration": 2.4, "industrial fan": 2.4, "fan": 1.8,
    "valve": 1.8, "bearing": 1.7, "lubrication": 1.7,
    "hydraulic": 1.5, "pneumatic": 1.5, "mro": 1.5,
}

WEAR_PARTS = {
    "compressor valve": 1.8, "packing ring": 1.7, "packing rings": 1.7,
    "rider ring": 1.8, "rider rings": 1.8, "packing case": 1.7,
    "packing cases": 1.7, "wear ring": 1.4, "wear rings": 1.4,
    "valve plate": 1.4, "ptfe": 0.8, "peek": 0.8,
}

TRANSFER = {
    "aftermarket": 0.8, "field service": 0.6, "technical support": 0.5,
    "product support": 0.6, "retrofit": 0.7, "upgrade": 0.5,
    "reliability": 0.6, "predictive maintenance": 0.7,
    "preventive maintenance": 0.5, "root cause": 0.5,
    "troubleshooting": 0.4, "site visit": 0.4, "customer site": 0.4,
    "territory": 0.4, "distributor": 0.4, "channel": 0.3,
    "proposal": 0.3, "quotation": 0.3, "commissioning": 0.4,
    "maintenance": 0.3,
}

INDUSTRY = {
    "refinery": 0.5, "petrochemical": 0.5, "oil and gas": 0.5,
    "power generation": 0.5, "mining": 0.5, "cement": 0.4,
    "steel": 0.4, "pulp and paper": 0.4, "chemical": 0.4,
    "manufacturing": 0.3, "industrial": 0.3,
}

NON_SALES_TITLE = [
    "finance", "accounting", "human resources", "software developer",
    "data analyst", "warehouse", "millwright", "journeyman", "mechanic",
    "maintenance technician", "vibration technician", "field technician",
    "service technician",
]

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def best_title_score(title):
    hits = [(k, w) for k, w in PRIMARY_SALES_TITLE.items() if k in title]
    if not hits:
        return 0.0, []
    best = max(w for _, w in hits)
    labels = [k for k, w in hits if w == best]
    return best, labels[:2]

def capped_term_score(text, terms, cap):
    hits, values = [], []
    for k, w in terms.items():
        if k in text:
            hits.append(k)
            values.append(w)
    if not values:
        return 0.0, []
    values.sort(reverse=True)
    total = values[0] + (sum(values[1:]) * 0.25 if len(values) > 1 else 0)
    return min(cap, total), hits

def score_job(job, config=None):
    title = norm(job.get("title"))
    text = norm(" ".join([job.get("title",""), job.get("description",""), job.get("company","")]))
    role_score, role_hits = best_title_score(title)

    if role_score == 0:
        if any(k in title for k in NON_SALES_TITLE):
            return 0.0, [], ["non-sales-title"], "excluded"
        return 0.0, [], ["no-sales-title"], "excluded"

    equipment_score, equipment_hits = capped_term_score(text, EQUIPMENT, 3.5)
    wear_score, wear_hits = capped_term_score(text, WEAR_PARTS, 0.8)
    transfer_score, transfer_hits = capped_term_score(text, TRANSFER, 1.5)
    industry_score, industry_hits = capped_term_score(text, INDUSTRY, 0.5)
    equipment_total = min(3.5, equipment_score + wear_score)

    target_bonus = 0.0
    if job.get("target_company"):
        tf = job.get("target_fit")
        target_bonus = min(0.5, max(0.25, tf * 0.05)) if isinstance(tf, (int, float)) else 0.4

    score = min(10.0, round(role_score + equipment_total + transfer_score + industry_score + target_bonus, 1))
    matched = list(dict.fromkeys(role_hits + equipment_hits + wear_hits + transfer_hits + industry_hits + (["target company"] if target_bonus else [])))

    category = "excellent" if score >= 9 else ("strong" if score >= 8 else ("good" if score >= 7 else ("match" if score >= 6 else "adjacent")))
    return score, matched, [], category
