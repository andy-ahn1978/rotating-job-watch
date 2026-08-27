import re
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

ROLE_WORDS = [
    "sales","account","manager","representative","engineer","specialist",
    "business development","territory","aftermarket","reliability",
    "condition monitoring","product support","advisor"
]

def norm(x):
    return re.sub(r"\s+"," ",x or "").strip()

def official_comairco(target):
    try:
        r=requests.get(target["careers_url"],headers={"User-Agent":"Mozilla/5.0 RotatingJobWatch/4.0"},timeout=30)
        r.raise_for_status()
    except Exception as e:
        print("Comairco official ERROR:",e)
        return []

    soup=BeautifulSoup(r.text,"html.parser")
    jobs=[]
    used=set()

    for a in soup.find_all("a",href=True):
        url=urljoin(target["careers_url"],a["href"])
        path=url.lower().split("comairco.com",1)[-1].split("?",1)[0].rstrip("/")
        if not path.startswith("/careers/") or path=="/careers":
            continue
        if url in used:
            continue

        block=a
        for _ in range(6):
            if block.parent is None: break
            block=block.parent
            if len(norm(block.get_text(" ",strip=True)))>40:
                break

        text=norm(block.get_text(" ",strip=True))
        heads=block.find_all(["h2","h3","h4","h5","strong"])
        candidates=[norm(h.get_text(" ",strip=True)) for h in heads]
        candidates=[x for x in candidates if any(w in x.lower() for w in ROLE_WORDS)]
        if candidates:
            title=candidates[0]
        else:
            title=norm(a.get_text(" ",strip=True))
        if title.lower() in {"see the detailed job offer","learn more","view"}:
            # URL slug is more useful than a generic anchor label.
            slug=path.split("/")[-1].replace("-"," ")
            title=slug.title()

        if not any(w in title.lower() for w in ROLE_WORDS):
            continue

        non_on=["saskatoon","alberta","quebec","laval","dartmouth","nova scotia","new brunswick",
                "boston","new york","syracuse","nashua","leominster","massachusetts"]
        low=text.lower()
        if any(x in low for x in non_on) and "all locations" not in low:
            continue

        loc="Ontario"
        for p in ["toronto","mississauga","hamilton","burlington","london","all locations"]:
            if p in low:
                loc=p.title()
                break

        used.add(url)
        jobs.append({
            "company":target["name"],"title":title,"location":loc,
            "description":text,"url":url,"source":"Official",
            "created":None,"external_id":hashlib.sha1(url.encode()).hexdigest()[:16]
        })

    print("Official [Comairco]:",len(jobs),"results")
    return jobs

def fetch_official_jobs(targets):
    out=[]
    for t in targets:
        if t["id"]=="comairco":
            out.extend(official_comairco(t))
    return out
