#!/usr/bin/env python3
import json
import re
from pathlib import Path

from score import score_job, build_tfidf_scores

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "jobs.json"
TARGETS_PATH = ROOT / "targets.json"
PROFILE_PATH = ROOT / "career_profile.json"

def norm_company(value):
    value = (value or "").lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(
        r"\b(inc|incorporated|ltd|limited|corp|corporation|company|co|canada|canadian|llc|lp)\b",
        " ",
        value,
    )
    return re.sub(r"\s+", " ", value).strip()

def target_match(company, targets):
    c = norm_company(company)
    if not c:
        return None

    for t in targets:
        name = t.get("name", "")
        aliases = [name]
        aliases.extend(re.split(r"[|/]", name))
        aliases.extend(t.get("aliases", []) or [])

        for alias in aliases:
            a = norm_company(alias)
            if len(a) < 4:
                continue
            if a == c or a in c or c in a:
                return t
    return None

if not JOBS_PATH.exists():
    raise SystemExit("jobs.json not found")

jobs_doc = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
jobs = jobs_doc.get("jobs", [])
targets = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

# Refresh target-company metadata from targets.json so short Adzuna descriptions
# can still be compared with the company's actual equipment/category.
for job in jobs:
    target = target_match(job.get("company"), targets)
    job["target_company"] = bool(target)
    job["target_fit"] = target.get("fit") if target else None
    job["target_category"] = target.get("category", "") if target else ""
    job["target_equipment"] = target.get("equipment", []) if target else []

tfidf_results = build_tfidf_scores(jobs, profile)

changed = 0
for job, tfidf in zip(jobs, tfidf_results):
    old_score = job.get("score")
    job["_tfidf"] = tfidf

    score_result = score_job(job)
    score, positive, negative = score_result[:3]

    job["score"] = score
    job["matched_keywords"] = positive[:8]
    job["negative_keywords"] = negative[:5]
    job["tfidf_similarity"] = tfidf.get("combined", 0.0)
    job.pop("_tfidf", None)

    if old_score != score:
        changed += 1

jobs.sort(key=lambda j: (
    not j.get("is_new", False),
    not j.get("target_company", False),
    -float(j.get("score", 0)),
    j.get("company", ""),
    j.get("title", ""),
))

jobs_doc["jobs"] = jobs
JOBS_PATH.write_text(
    json.dumps(jobs_doc, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print(f"Re-scored {len(jobs)} existing jobs. Scores changed: {changed}. Adzuna API calls: 0.")
