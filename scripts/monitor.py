#!/usr/bin/env python3
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone

from adzuna import fetch_adzuna_jobs
from official import fetch_official_jobs
from score import score_job, build_tfidf_scores

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "search_config.json").read_text(encoding="utf-8"))
TARGETS = json.loads((ROOT / "targets.json").read_text(encoding="utf-8"))
PROFILE = json.loads((ROOT / "career_profile.json").read_text(encoding="utf-8"))

JOBS_PATH = ROOT / "jobs.json"
SEEN_PATH = ROOT / "seen_jobs.json"

STRONG_TECH = [
    "rotating equipment", "rotating machinery", "industrial machinery",
    "industrial equipment", "process equipment", "turbomachinery",
    "reciprocating", "reciprocating compressor", "centrifugal compressor",
    "diaphragm compressor", "air compressor", "compressor", "compressed air",
    "blower", "industrial fan", "vacuum pump", "mechanical seal",
    "condition monitoring", "vibration analysis", "predictive maintenance",
    "asset reliability", "reliability", "pump", "pumps", "hydraulic",
    "pneumatic", "mro"
]

WEAR_PARTS = [
    "packing ring", "packing rings", "piston ring", "piston rings",
    "rider ring", "rider rings", "wear ring", "wear rings",
    "packing case", "packing cases", "compressor valve", "compressor valves",
    "valve plate", "valve plates", "ptfe", "peek", "wear parts"
]

INDUSTRIAL_CONTEXT = [
    "compressor", "pump", "rotating", "industrial", "machinery", "equipment",
    "refinery", "petrochemical", "chemical", "power generation",
    "oil and gas", "mining", "process", "manufacturing", "maintenance"
]

def _contains(text, terms):
    return any(term in text for term in terms)

def passes_general_gate(job):
    text = " ".join([
        job.get("title") or "",
        job.get("company") or "",
        job.get("description") or "",
    ]).lower()

    if _contains(text, STRONG_TECH):
        return True
    if _contains(text, WEAR_PARTS) and _contains(text, INDUSTRIAL_CONTEXT):
        return True
    return False

def canonical_key(job):
    eid = (job.get("external_id") or "").strip()
    if eid:
        return f"{job.get('source', '')}:{eid}"
    text = "|".join([
        (job.get("company") or "").lower().strip(),
        (job.get("title") or "").lower().strip(),
        (job.get("location") or "").lower().strip(),
    ])
    return hashlib.sha1(text.encode()).hexdigest()

def title_company_key(job):
    return "|".join([
        (job.get("company") or "").lower().strip(),
        (job.get("title") or "").lower().strip(),
        (job.get("location") or "").lower().strip(),
    ])

def norm_company(value):
    value = (value or "").lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(
        r"\b(inc|incorporated|ltd|limited|corp|corporation|company|co|canada|canadian|llc|lp)\b",
        " ", value,
    )
    return re.sub(r"\s+", " ", value).strip()

def target_match(company):
    c = norm_company(company)
    if not c:
        return None
    for t in TARGETS:
        name = t.get("name", "")
        aliases = [name]
        aliases.extend(re.split(r"[|/]", name))
        aliases.extend(t.get("aliases", []))
        for alias in aliases:
            a = norm_company(alias)
            if len(a) < 4:
                continue
            if a == c or a in c or c in a:
                return t
    return None

old = json.loads(JOBS_PATH.read_text(encoding="utf-8")) if JOBS_PATH.exists() else {"jobs": []}
old_first = {j.get("key"): j.get("first_seen") for j in old.get("jobs", []) if j.get("key")}

seen = json.loads(SEEN_PATH.read_text(encoding="utf-8")) if SEEN_PATH.exists() else {
    "initialized": False, "ids": [],
}
seen_ids = set(seen.get("ids", []))
initialized = bool(seen.get("initialized", False))
now = datetime.now(timezone.utc).isoformat()

raw = []
raw.extend(fetch_adzuna_jobs(CONFIG))
raw.extend(fetch_official_jobs(TARGETS))

# Add target-company metadata before TF-IDF. This solves short/trimmed JD cases:
# the model can still see what the target company actually sells/services.
eligible = []
gate_rejected = 0
for job in raw:
    if not job.get("title") or not job.get("url"):
        continue

    target = target_match(job.get("company"))
    job["target_company"] = bool(target)
    job["target_fit"] = target.get("fit") if target else None
    job["target_category"] = target.get("category", "") if target else ""
    job["target_equipment"] = target.get("equipment", []) if target else []

    if not target and job.get("search_type") == "keyword":
        if not passes_general_gate(job):
            gate_rejected += 1
            continue

    eligible.append(job)

tfidf_results = build_tfidf_scores(eligible, PROFILE)
for job, tfidf in zip(eligible, tfidf_results):
    job["_tfidf"] = tfidf

dedup = {}
minimum_score = float(CONFIG.get("minimum_score", 5.0))
target_minimum_score = float(CONFIG.get("target_minimum_score", 3.0))

for job in eligible:
    score_result = score_job(job, CONFIG)
    score, positive, negative = score_result[:3]

    required_score = target_minimum_score if job.get("target_company") else minimum_score
    if score < required_score:
        continue

    job["score"] = score
    job["matched_keywords"] = positive[:8]
    job["negative_keywords"] = negative[:5]
    job["tfidf_similarity"] = job.get("_tfidf", {}).get("combined", 0.0)
    job.pop("_tfidf", None)

    tkey = title_company_key(job)
    existing = dedup.get(tkey)
    if not existing or (existing.get("source") != "Official" and job.get("source") == "Official"):
        dedup[tkey] = job

jobs = list(dedup.values())
for j in jobs:
    j["key"] = canonical_key(j)
    j["first_seen"] = old_first.get(j["key"]) or now
    j["is_new"] = initialized and j["key"] not in seen_ids

jobs.sort(key=lambda j: (
    not j["is_new"],
    not j.get("target_company", False),
    -j["score"],
    j["company"],
    j["title"],
))

JOBS_PATH.write_text(
    json.dumps({"last_checked": now, "jobs": jobs}, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

ids = {j["key"] for j in jobs}
SEEN_PATH.write_text(
    json.dumps({"initialized": True, "ids": sorted(seen_ids | ids)}, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

new = [j for j in jobs if j["is_new"]]
(ROOT / "new_jobs.json").write_text(
    json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8"
)

target_jobs = sum(1 for j in jobs if j.get("target_company"))
print(
    f"V6.3 TF-IDF Search: raw={len(raw)}, eligible={len(eligible)}, "
    f"qualified={len(jobs)}, target_jobs={target_jobs}, "
    f"gate_rejected={gate_rejected}, new={len(new)}"
)
