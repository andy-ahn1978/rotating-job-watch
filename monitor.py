#!/usr/bin/env python3
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone

from adzuna import fetch_adzuna_jobs
from official import fetch_official_jobs
from score import score_job

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/"search_config.json").read_text())
TARGETS = json.loads((ROOT/"targets.json").read_text())
JOBS_PATH = ROOT/"jobs.json"
SEEN_PATH = ROOT/"seen_jobs.json"

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def target_match(company):
    c = norm(company)
    for t in TARGETS:
        names = [norm(t["name"])]
        if t["id"] == "dxp-natpro":
            names += ["dxp", "natpro"]
        if t["id"] == "atlas-copco":
            names += ["atlas copco"]
        if any(n and (n in c or c in n) for n in names):
            return t
    return None

def duplicate_key(job):
    company = norm(job.get("company"))
    # Normalize common company suffixes so Flender variants collapse.
    for suffix in [
        " corporation pe canada", " corporation canada", " corporation",
        " company", " inc", " ltd", " limited"
    ]:
        company = company.replace(suffix, "")
    title = norm(job.get("title"))
    desc = norm(job.get("description"))[:500]
    return hashlib.sha1(f"{company}|{title}|{desc}".encode()).hexdigest()

def stable_key(job):
    eid = (job.get("external_id") or "").strip()
    if eid:
        return f"{job.get('source','')}:{eid}"
    return duplicate_key(job)

def wrong_province(job):
    d = (job.get("description") or "").lower()
    loc = (job.get("location") or "").lower()

    looks_ontario = (
        "ontario" in loc or
        any(x in loc for x in [
            "toronto","peel","waterloo","hamilton","ottawa","halton",
            "sarnia","mississauga","brampton","cambridge","kitchener"
        ])
    )
    if not looks_ontario:
        return False

    explicit_outside = [
        "richmond, bc", "richmond bc", "british columbia",
        "vancouver, bc", "vancouver bc",
        "calgary, ab", "calgary ab", "edmonton, ab", "edmonton ab",
        "alberta"
    ]
    return any(x in d for x in explicit_outside)

old_payload = json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else {"jobs":[]}
old_first_seen = {
    j.get("key"): j.get("first_seen")
    for j in old_payload.get("jobs", [])
    if j.get("key")
}

seen_raw = json.loads(SEEN_PATH.read_text()) if SEEN_PATH.exists() else {"initialized":False,"ids":[]}
if isinstance(seen_raw, dict) and "ids" in seen_raw:
    initialized = bool(seen_raw.get("initialized", False))
    seen_ids = set(seen_raw.get("ids", []))
else:
    initialized = True
    seen_ids = set(seen_raw.keys()) if isinstance(seen_raw, dict) else set(seen_raw or [])

now = datetime.now(timezone.utc).isoformat()

raw = []
raw.extend(fetch_adzuna_jobs(CONFIG))
raw.extend(fetch_official_jobs(TARGETS))
print(f"V4.1.1 raw={len(raw)}")

qualified = []
dedupe = {}

for job in raw:
    if not job.get("title") or not job.get("url"):
        continue

    if wrong_province(job):
        continue

    target = target_match(job.get("company"))
    job["target_company"] = bool(target)
    job["target_fit"] = target.get("fit") if target else None

    score, positive, negative = score_job(job, CONFIG)

    if target:
        score = min(10.0, round(score + 1.0, 1))
        if "target company" not in positive:
            positive.append("target company")

    # Keep only career-relevant jobs.
    if score < 5.0:
        continue

    job["score"] = score
    job["matched_keywords"] = positive[:10]
    job["negative_keywords"] = negative[:5]
    job["fit_category"] = "strong" if score >= 7.0 else "match"

    dk = duplicate_key(job)
    existing = dedupe.get(dk)
    if existing is None:
        dedupe[dk] = job
    else:
        # Prefer official source if duplicate appears in multiple sources.
        if existing.get("source") != "Official" and job.get("source") == "Official":
            dedupe[dk] = job

qualified = list(dedupe.values())

for job in qualified:
    job["key"] = stable_key(job)
    job["first_seen"] = old_first_seen.get(job["key"]) or now
    job["is_new"] = initialized and job["key"] not in seen_ids

qualified.sort(key=lambda j: (
    not j.get("is_new", False),
    -j.get("score", 0),
    j.get("company",""),
    j.get("title","")
))

JOBS_PATH.write_text(json.dumps({
    "last_checked": now,
    "jobs": qualified
}, indent=2, ensure_ascii=False))

all_ids = {j["key"] for j in qualified}
SEEN_PATH.write_text(json.dumps({
    "initialized": True,
    "ids": sorted(seen_ids | all_ids)
}, indent=2))

new_jobs = [j for j in qualified if j.get("is_new")]
(ROOT/"new_jobs.json").write_text(json.dumps({
    "last_checked": now,
    "jobs": new_jobs
}, indent=2, ensure_ascii=False))

print(
    f"V4.1.1 qualified={len(qualified)}, "
    f"new={len(new_jobs)}, "
    f"strong={sum(j['score'] >= 7 for j in qualified)}"
)
