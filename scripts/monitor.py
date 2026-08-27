#!/usr/bin/env python3
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from adzuna import fetch_adzuna_jobs
from official import fetch_official_jobs
from score import score_job

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/"search_config.json").read_text())
TARGETS=json.loads((ROOT/"targets.json").read_text())
JOBS_PATH=ROOT/"jobs.json"
SEEN_PATH=ROOT/"seen_jobs.json"

def canonical_key(job):
    # Prefer source ID when available, otherwise normalized company/title/location.
    eid=(job.get("external_id") or "").strip()
    if eid:
        return f"{job.get('source','')}:{eid}"
    text="|".join([
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

def target_match(company):
    c=(company or "").lower()
    for t in TARGETS:
        aliases=[t["name"].lower()]
        if t["id"]=="dxp-natpro": aliases+=["natpro","dxp"]
        if t["id"]=="atlas-copco": aliases+=["atlas copco"]
        if any(a in c or c in a for a in aliases if len(a)>2):
            return t
    return None

old=json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else {"jobs":[]}
old_first={j.get("key"):j.get("first_seen") for j in old.get("jobs",[]) if j.get("key")}
seen=json.loads(SEEN_PATH.read_text()) if SEEN_PATH.exists() else {"initialized":False,"ids":[]}
seen_ids=set(seen.get("ids",[]))
initialized=bool(seen.get("initialized",False))
now=datetime.now(timezone.utc).isoformat()

raw=[]
raw.extend(fetch_adzuna_jobs(CONFIG))
raw.extend(fetch_official_jobs(TARGETS))

# Deduplicate across queries and across sources.
dedup={}
for job in raw:
    if not job.get("title") or not job.get("url"):
        continue
    score,positive,negative=score_job(job,CONFIG)
    if score < float(CONFIG.get("minimum_score",5)):
        continue

    job["score"]=score
    job["matched_keywords"]=positive[:8]
    job["negative_keywords"]=negative[:5]
    target=target_match(job.get("company"))
    job["target_company"]=bool(target)
    job["target_fit"]=target.get("fit") if target else None
    # Target companies receive a small ranking benefit, but score remains capped.
    if target:
        job["score"]=min(10.0,round(job["score"]+1.0,1))

    tkey=title_company_key(job)
    existing=dedup.get(tkey)
    if not existing:
        dedup[tkey]=job
    else:
        # Prefer Official over Adzuna if the same role appears twice.
        if existing.get("source")!="Official" and job.get("source")=="Official":
            dedup[tkey]=job

jobs=list(dedup.values())
for j in jobs:
    j["key"]=canonical_key(j)
    j["first_seen"]=old_first.get(j["key"]) or now
    j["is_new"]=initialized and j["key"] not in seen_ids

jobs.sort(key=lambda j:(not j["is_new"],-j["score"],j["company"],j["title"]))
JOBS_PATH.write_text(json.dumps({"last_checked":now,"jobs":jobs},indent=2,ensure_ascii=False))

ids={j["key"] for j in jobs}
SEEN_PATH.write_text(json.dumps({"initialized":True,"ids":sorted(seen_ids|ids)},indent=2))
new=[j for j in jobs if j["is_new"]]
(ROOT/"new_jobs.json").write_text(json.dumps(new,indent=2,ensure_ascii=False))

print(f"V4: raw={len(raw)}, qualified={len(jobs)}, new={len(new)}")
