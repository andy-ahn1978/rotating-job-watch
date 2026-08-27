import re

SALES_TITLE = [
    "technical sales", "sales engineer", "sales representative", "sales specialist",
    "territory sales", "territory manager", "account manager", "outside sales",
    "business development", "aftermarket sales", "product support sales",
    "retrofit specialist", "commercial manager", "sales manager"
]
TECH = {
    "rotating equipment": 1.5, "compressor": 1.2, "pump": 1.2, "blower": 1.0,
    "fan": 0.8, "valve": 0.8, "condition monitoring": 1.0, "vibration": 0.7,
    "reliability": 0.8, "mechanical": 0.5, "hydraulic": 0.6, "mro": 0.6
}
INDUSTRY = {
    "refinery": .5, "petrochemical": .5, "oil and gas": .5, "power generation": .5,
    "mining": .5, "cement": .5, "manufacturing": .4, "industrial": .4
}
NON_SALES_TITLE = [
    "millwright", "journeyman", "mechanic", "maintenance technician",
    "vibration technician", "field technician", "service technician"
]

def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def score_job(job):
    title=norm(job.get("title"))
    text=norm(" ".join([job.get("title",""),job.get("description",""),job.get("company","")]))
    sales_hits=[k for k in SALES_TITLE if k in title]
    non_sales=any(k in title for k in NON_SALES_TITLE)

    # Sales-first gate: eliminate hands-on trade/technician jobs unless title itself is sales/commercial.
    if non_sales and not sales_hits:
        return 0.0, [], ["non-sales-title"], "excluded"

    score=0.0
    matched=[]
    if sales_hits:
        score += min(4.5, 2.5 + 0.7*(len(sales_hits)-1))
        matched += sales_hits

    for k,w in TECH.items():
        if k in text:
            score += w
            matched.append(k)
    for k,w in INDUSTRY.items():
        if k in text:
            score += w
            matched.append(k)

    if job.get("target_company"):
        score += 1.0
        matched.append("target company")

    score=min(10.0, round(score,1))
    category = "strong" if score >= 7.0 else ("match" if score >= 5.0 else "adjacent")
    return score, list(dict.fromkeys(matched)), [], category
