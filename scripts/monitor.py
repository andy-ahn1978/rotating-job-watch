#!/usr/bin/env python3
import json, re, hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
targets=json.loads((ROOT/"targets.json").read_text())
seen_path=ROOT/"seen_jobs.json"; jobs_path=ROOT/"jobs.json"
seen=json.loads(seen_path.read_text()) if seen_path.exists() else {"initialized":False,"ids":[]}
seen_ids=set(seen.get("ids",[])); initialized=bool(seen.get("initialized",False))

GLOBAL=[
 "technical sales","sales representative","sales engineer","account manager","territory sales","aftermarket",
 "business development","product support","service sales","reliability","condition monitoring","rotating equipment",
 "compressor","pump","blower","retrofit","service specialist","sales specialist"
]

def norm(s): return re.sub(r"\s+"," ",s or "").strip()
def make_id(cid,title,url): return hashlib.sha1(f"{cid}|{title.lower()}|{url}".encode()).hexdigest()[:20]

def parse_links(html,base):
 soup=BeautifulSoup(html,"html.parser"); out=[]
 for a in soup.find_all("a",href=True):
   title=norm(a.get_text(" ",strip=True)); url=urljoin(base,a["href"])
   if len(title)<4: continue
   blob=(title+" "+url).lower()
   if any(x in blob for x in ["job","career","position","vacanc","opening","sales","account","service","reliability","engineer","specialist"]):
      out.append((title,url))
 return out

def check(t):
 try:
   r=requests.get(t["careers_url"],headers={"User-Agent":"Mozilla/5.0 RotatingJobWatch/3.0"},timeout=25)
   r.raise_for_status()
 except Exception as e:
   print("ERROR",t["name"],e);return []
 out={}
 for title,url in parse_links(r.text,t["careers_url"]):
   blob=(title+" "+url).lower()
   matched=sorted({k for k in GLOBAL+t.get("keywords",[]) if k in blob})
   if not matched: continue
   if any(x in blob for x in ["united states","california","texas","florida","new york, ny"]): continue
   j={"id":make_id(t["id"],title,url),"company_id":t["id"],"company":t["name"],"title":title,
      "location":t["region"],"url":url,"careers_url":t["careers_url"],"fit":t["fit"],"matched_keywords":matched[:6]}
   out[j["id"]]=j
 return list(out.values())

old=json.loads(jobs_path.read_text()) if jobs_path.exists() else {"jobs":[]}
first={j["id"]:j.get("first_seen") for j in old.get("jobs",[])}
now=datetime.now(timezone.utc).isoformat()
all_jobs=[]
for t in targets: all_jobs.extend(check(t))
for j in all_jobs:
 j["first_seen"]=first.get(j["id"]) or now
 j["is_new"]=initialized and j["id"] not in seen_ids
jobs_path.write_text(json.dumps({"last_checked":now,"jobs":sorted(all_jobs,key=lambda x:(not x["is_new"],-x["fit"],x["company"]))},indent=2,ensure_ascii=False))
all_ids={j["id"] for j in all_jobs}
seen_path.write_text(json.dumps({"initialized":True,"ids":sorted(seen_ids|all_ids)},indent=2))
(ROOT/"new_jobs.json").write_text(json.dumps([j for j in all_jobs if j["is_new"]],indent=2,ensure_ascii=False))
print("targets",len(targets),"jobs",len(all_jobs),"new",sum(1 for j in all_jobs if j["is_new"]))
