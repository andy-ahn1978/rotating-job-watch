#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TARGETS = json.loads((ROOT/"targets.json").read_text())
JOBS_PATH = ROOT/"jobs.json"
SEEN_PATH = ROOT/"seen_jobs.json"

ROLE_WORDS = [
    "sales","account","manager","representative","engineer","specialist",
    "business development","territory","aftermarket","reliability",
    "condition monitoring","product support","advisor"
]

ONTARIO_TERMS = [
    "ontario","toronto","mississauga","burlington","hamilton","stoney creek",
    "sarnia","cambridge","kitchener","guelph","sudbury","oakville","london",
    "windsor","niagara","brampton","etobicoke","all locations"
]

def norm(x):
    return re.sub(r"\s+"," ",x or "").strip()

def jid(cid,title,url):
    return hashlib.sha1(f"{cid}|{title.lower()}|{url}".encode()).hexdigest()[:20]

def fetch(url):
    r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 RotatingJobWatch/3.2"},timeout=30)
    r.raise_for_status()
    return r.text

def role_relevant(title,target):
    t=title.lower()
    target_words=target.get("keywords",[])
    matched=sorted({k for k in target_words if k.lower() in t})
    strong=any(w in t for w in ROLE_WORDS)
    return strong,matched

def ontario_relevant(location):
    l=(location or "").lower()
    return any(x in l for x in ONTARIO_TERMS)

def parse_comairco(target):
    html=fetch(target["careers_url"])
    soup=BeautifulSoup(html,"html.parser")
    jobs=[]
    seen_urls=set()

    # Actual job detail links on Comairco are under /careers/<job-slug>/
    for a in soup.find_all("a",href=True):
        url=urljoin(target["careers_url"],a["href"])
        path=url.lower().split("comairco.com",1)[-1].split("?",1)[0].rstrip("/")
        if not path.startswith("/careers/") or path=="/careers":
            continue
        if url in seen_urls:
            continue

        # Find the containing block to recover title/location.
        block=a
        for _ in range(5):
            if block.parent is None: break
            block=block.parent
            text=norm(block.get_text(" ",strip=True))
            if len(text)>20:
                break
        text=norm(block.get_text(" ",strip=True))
        # Prefer heading text in the same block.
        heading=block.find(["h2","h3","h4","h5","strong"])
        title=norm(heading.get_text(" ",strip=True)) if heading else norm(a.get_text(" ",strip=True))
        if title.lower() in {"see the detailed job offer","learn more","view"} or len(title)<4:
            # infer first meaningful line before the link label
            chunks=[norm(x) for x in re.split(r"\s{2,}|\|",text) if norm(x)]
            title=next((x for x in chunks if any(w in x.lower() for w in ROLE_WORDS)), title)

        strong,matched=role_relevant(title,target)
        if not strong:
            continue

        location="Ontario"
        for term in ONTARIO_TERMS:
            if term in text.lower():
                location=term.title()
                break

        # Exclude clearly non-Ontario locations unless "All locations".
        non_on=["saskatoon","alberta","quebec","laval","dartmouth","nova scotia","new brunswick",
                "boston","new york","syracuse","nashua","leominster","massachusetts"]
        if any(x in text.lower() for x in non_on) and "all locations" not in text.lower():
            continue

        seen_urls.add(url)
        jobs.append({
            "id":jid(target["id"],title,url),
            "company_id":target["id"],
            "company":target["name"],
            "title":title,
            "location":location,
            "url":url,
            "careers_url":target["careers_url"],
            "source":"Official",
            "fit":target["fit"],
            "matched_keywords":matched
        })
    return jobs

def parse_generic_job_urls(target):
    # Conservative fallback only for targets explicitly marked direct later.
    html=fetch(target["careers_url"])
    soup=BeautifulSoup(html,"html.parser")
    jobs=[]
    for a in soup.find_all("a",href=True):
        title=norm(a.get_text(" ",strip=True))
        url=urljoin(target["careers_url"],a["href"])
        u=url.lower()
        if not any(p in u for p in ["/job-detail/","/job/","/jobs/","/careers/"]):
            continue
        if u.rstrip("/")==target["careers_url"].lower().rstrip("/"):
            continue
        strong,matched=role_relevant(title,target)
        if not strong:
            continue
        jobs.append({
            "id":jid(target["id"],title,url),"company_id":target["id"],"company":target["name"],
            "title":title,"location":target["region"],"url":url,"careers_url":target["careers_url"],
            "source":"Official","fit":target["fit"],"matched_keywords":matched
        })
    unique={j["id"]:j for j in jobs}
    return list(unique.values())

def check_target(target):
    if target.get("monitor_mode")!="direct":
        print(f"{target['name']}: external-only")
        return []
    try:
        if target["id"]=="comairco":
            jobs=parse_comairco(target)
        else:
            jobs=parse_generic_job_urls(target)
        print(f"{target['name']}: {len(jobs)} validated jobs")
        return jobs
    except Exception as e:
        print(f"{target['name']}: ERROR {e}")
        return []

old=json.loads(JOBS_PATH.read_text()) if JOBS_PATH.exists() else {"jobs":[]}
old_first={j["id"]:j.get("first_seen") for j in old.get("jobs",[])}
seen=json.loads(SEEN_PATH.read_text()) if SEEN_PATH.exists() else {"initialized":False,"ids":[]}
seen_ids=set(seen.get("ids",[]))
initialized=bool(seen.get("initialized",False))
now=datetime.now(timezone.utc).isoformat()

jobs=[]
for t in TARGETS:
    jobs.extend(check_target(t))

for j in jobs:
    j["first_seen"]=old_first.get(j["id"]) or now
    j["is_new"]=initialized and j["id"] not in seen_ids

jobs=sorted(jobs,key=lambda j:(not j["is_new"],-j["fit"],j["company"],j["title"]))
JOBS_PATH.write_text(json.dumps({"last_checked":now,"jobs":jobs},indent=2,ensure_ascii=False))

all_ids={j["id"] for j in jobs}
SEEN_PATH.write_text(json.dumps({"initialized":True,"ids":sorted(seen_ids|all_ids)},indent=2))
(ROOT/"new_jobs.json").write_text(json.dumps([j for j in jobs if j["is_new"]],indent=2,ensure_ascii=False))

print(f"Checked {len(TARGETS)} targets; {len(jobs)} validated official jobs; {sum(j['is_new'] for j in jobs)} new.")
