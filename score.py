import re

SALES_TITLE_TERMS = [
    "technical sales", "sales engineer", "sales representative", "sales specialist",
    "territory sales", "territory manager", "account manager", "outside sales",
    "business development", "aftermarket sales", "product support sales",
    "retrofit specialist", "commercial manager", "sales manager", "industrial sales"
]

NON_SALES_TITLE_TERMS = [
    "millwright", "millwight", "journeyman", "mechanic",
    "maintenance technician", "vibration technician",
    "field technician", "service technician"
]

TECH_WEIGHTS = {
    "rotating equipment": 1.6,
    "compressor": 1.4,
    "reciprocating": 1.0,
    "pump": 1.2,
    "blower": 1.0,
    "fan": 0.7,
    "valve": 0.7,
    "condition monitoring": 1.2,
    "vibration": 0.8,
    "reliability": 0.8,
    "alignment": 0.7,
    "retrofit": 1.2,
    "aftermarket": 1.2,
    "product support": 0.8,
    "hydraulic": 0.6,
    "mro": 0.6,
    "mechanical": 0.4,
}

INDUSTRY_WEIGHTS = {
    "refinery": 0.5,
    "petrochemical": 0.5,
    "oil and gas": 0.5,
    "power generation": 0.5,
    "mining": 0.5,
    "cement": 0.4,
    "manufacturing": 0.4,
    "industrial": 0.4,
}

def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def score_job(job, config=None):
    title = _norm(job.get("title"))
    blob = _norm(" ".join([
        job.get("title",""),
        job.get("company",""),
        job.get("description",""),
        job.get("location","")
    ]))

    # Hard filter obvious trade/technician roles unless explicitly sales/commercial.
    sales_title_hits = [t for t in SALES_TITLE_TERMS if t in title]
    if any(t in title for t in NON_SALES_TITLE_TERMS) and not sales_title_hits:
        return 0.0, [], ["non-sales-title"]

    score = 0.0
    matched = []

    # Job-title relevance is the strongest signal.
    if sales_title_hits:
        score += min(4.5, 3.0 + 0.5 * (len(sales_title_hits)-1))
        matched.extend(sales_title_hits)

    # Allow role keywords from existing config as extra evidence.
    if config:
        for term, value in config.get("positive_terms", {}).items():
            term_l = term.lower()
            if term_l in blob and term_l not in matched:
                # Cap generic configured weights so they cannot overpower title relevance.
                score += min(float(value), 1.2)
                matched.append(term_l)

    for term, weight in TECH_WEIGHTS.items():
        if term in blob and term not in matched:
            score += weight
            matched.append(term)

    for term, weight in INDUSTRY_WEIGHTS.items():
        if term in blob and term not in matched:
            score += weight
            matched.append(term)

    # Existing config negative terms.
    negatives = []
    if config:
        for term, value in config.get("negative_terms", {}).items():
            if term.lower() in blob:
                score += float(value)
                negatives.append(term.lower())

    # Ontario/city evidence.
    ontario_places = [
        "ontario","toronto","mississauga","hamilton","burlington","oakville",
        "cambridge","kitchener","guelph","sarnia","sudbury","london","windsor",
        "niagara","brampton","etobicoke","ottawa"
    ]
    if any(p in blob for p in ontario_places):
        score += 0.8

    score = max(0.0, min(10.0, round(score, 1)))
    return score, list(dict.fromkeys(matched)), negatives
