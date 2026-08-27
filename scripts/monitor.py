#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TARGETS = json.loads((ROOT / "targets.json").read_text())
SEEN_PATH = ROOT / "seen_jobs.json"
JOBS_PATH = ROOT / "jobs.json"

seen = json.loads(SEEN_PATH.read_text()) if SEEN_PATH.exists() else {
    "initialized": False,
    "ids": []
}
seen_ids = set(seen.get("ids", []))
initialized = bool(seen.get("initialized", False))

ROLE_KEYWORDS = [
    "technical sales",
    "sales representative",
    "sales engineer",
    "account manager",
    "territory sales",
    "territory manager",
    "aftermarket sales",
    "aftermarket",
    "business development",
    "product support",
    "service sales",
    "reliability",
    "condition monitoring",
    "rotating equipment",
    "compressor",
    "pump",
    "blower",
    "retrofit",
    "sales specialist",
    "account executive",
]

GENERIC_TITLES = {
    "home", "services", "service", "products", "product", "about", "about us",
    "contact", "contact us", "careers", "career", "jobs", "job opportunities",
    "learn more", "read more", "view", "view more", "request service",
    "parts", "equipment", "solutions", "industries", "privacy policy",
    "terms & conditions", "terms and conditions", "accessibility standards",
}

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()

def make_id(company_id, title, url):
    raw = f"{company_id}|{title.lower()}|{url}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]

def is_bad_scheme(url):
    return url.startswith(("mailto:", "tel:", "javascript:", "#"))

def clean_url(base, href):
    if not href:
        return None
    url = urljoin(base, href)
    if is_bad_scheme(url):
        return None
    return url

def extract_links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        title = norm(a.get_text(" ", strip=True))
        url = clean_url(base, a.get("href"))
        if not url or not title:
            continue
        links.append((title, url))
    return links

def title_looks_like_job(title):
    t = title.lower().strip()
    if t in GENERIC_TITLES:
        return False
    if len(t) < 5:
        return False
    strong = [
        "sales", "account manager", "manager", "specialist", "engineer",
        "representative", "business development", "advisor", "coordinator",
        "technician", "supervisor", "director", "leader"
    ]
    return any(k in t for k in strong)

def matched_keywords(title, target):
    blob = title.lower()
    kws = ROLE_KEYWORDS + target.get("keywords", [])
    return sorted({k for k in kws if k in blob})

def url_is_job_detail(target, url, title):
    cid = target["id"]
    u = url.lower()

    if cid == "atlas-copco":
        return "/jobs/" in u and (
            "/job-detail/" in u
            or "job-detail" in u
        ) and title_looks_like_job(title)

    if cid == "ingersoll-rand":
        return (
            "careers.irco.com" in u
            and any(x in u for x in ["/job/", "/jobdetail/", "/job-detail/", "/jobs/"])
            and title_looks_like_job(title)
        )

    if cid == "sulzer":
        return (
            "jobs.sulzer.com" in u
            and any(x in u for x in ["/job/", "/jobdetail/", "/job-detail/"])
            and title_looks_like_job(title)
        )

    if cid == "ksb":
        return (
            any(x in u for x in ["jobs.ksb.com", "/career/job", "/career/jobs", "/job/"])
            and title_looks_like_job(title)
        )

    if cid == "comairco":
        p = urlparse(u).path.rstrip("/")
        return (
            p.startswith("/careers/")
            and p != "/careers"
            and title_looks_like_job(title)
        )

    if cid == "john-brooks":
        return (
            any(x in u for x in ["/career-opportunities/", "/careers/", "/jobs/", "/job/"])
            and "join-our-team" not in u
            and title_looks_like_job(title)
        )

    if cid == "dxp-natpro":
        return (
            any(x in u for x in ["/job/", "/jobs/", "/careers/job", "/career/job"])
            and title_looks_like_job(title)
        )

    if cid in {
        "avt", "pneuair", "blowvac", "red-systems", "trade-mark",
        "emnor", "precision-concepts", "ips", "turbinepros"
    }:
        return (
            any(x in u for x in ["/careers/", "/career/", "/jobs/", "/job/"])
            and title_looks_like_job(title)
        )

    return (
        any(x in u for x in ["/careers/", "/career/", "/jobs/", "/job/"])
        and title_looks_like_job(title)
    )

def check_target(target):
    url = target["careers_url"]

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 RotatingJobWatch/3.1"},
            timeout=25
        )
        r.raise_for_status()
    except Exception as e:
        print("ERROR", target["name"], e)
        return []

    results = {}
    for title, link in extract_links(r.text, url):
        if not url_is_job_detail(target, link, title):
            continue

        matched = matched_keywords(title, target)
        if not matched:
            continue

        jid = make_id(target["id"], title, link)
        results[jid] = {
            "id": jid,
            "company_id": target["id"],
            "company": target["name"],
            "title": title,
            "location": target["region"],
            "url": link,
            "careers_url": target["careers_url"],
            "fit": target["fit"],
            "matched_keywords": matched[:6],
        }

    return list(results.values())

old_payload = json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else {"jobs": []}
old_first_seen = {
    j["id"]: j.get("first_seen")
    for j in old_payload.get("jobs", [])
}

now = datetime.now(timezone.utc).isoformat()
all_jobs = []

for target in TARGETS:
    found = check_target(target)
    print(f"{target['name']}: {len(found)} job candidates")
    all_jobs.extend(found)

for job in all_jobs:
    job["first_seen"] = old_first_seen.get(job["id"]) or now
    job["is_new"] = initialized and job["id"] not in seen_ids

all_jobs = sorted(
    all_jobs,
    key=lambda x: (
        not x["is_new"],
        -x["fit"],
        x["company"],
        x["title"]
    )
)

payload = {
    "last_checked": now,
    "jobs": all_jobs
}
JOBS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

all_ids = {j["id"] for j in all_jobs}
SEEN_PATH.write_text(json.dumps({
    "initialized": True,
    "ids": sorted(seen_ids | all_ids)
}, indent=2))

new_jobs = [j for j in all_jobs if j["is_new"]]
(ROOT / "new_jobs.json").write_text(
    json.dumps(new_jobs, indent=2, ensure_ascii=False)
)

print(
    f"Checked {len(TARGETS)} targets; "
    f"{len(all_jobs)} validated job links; "
    f"{len(new_jobs)} new."
)
