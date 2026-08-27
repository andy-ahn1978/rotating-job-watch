import json, os, re, hashlib
from datetime import datetime, timezone
from adzuna import search_all
from official import search_official
from score import score_job

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def norm(s):
    return re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).strip()

def dedupe_key(j):
    # Handles reposts where company suffix/location/external ID differs.
    company=norm(j.get("company",""))
    for suffix in [" corporation pe canada"," corporation canada"," company"," inc"," ltd"," limited"]:
        company=company.replace(suffix,"")
    title=norm(j.get("title",""))
    desc=norm(j.get("description",""))[:500]
    return hashlib.sha1((company+"|"+title+"|"+desc).encode()).hexdigest()

def wrong_province(j):
    # Adzuna occasionally maps a city name to Ontario while description explicitly says another province.
    d=(j.get("description") or "").lower()
    loc=(j.get("location") or "").lower()
    if "ontario" not in loc and not any(x in loc for x in ["toronto","peel","waterloo","hamilton","ottawa","halton","sarnia"]):
        return False
    outside=["richmond, bc","british columbia","calgary, ab","edmonton, ab","alberta","vancouver, bc"]
    return any(x in d for x in outside)

cfg=load("search_config.json",{})
targets=load("targets.json",[])
target_names={norm(t.get("company","")):t for t in targets}

raw=[]
raw += search_all(cfg)
raw += search_official(targets)
print(f"V4.1 raw={len(raw)}")

out=[]
seen=set()
for j in raw:
    cname=norm(j.get("company",""))
    for tn,t in target_names.items():
        if tn and (tn in cname or cname in tn):
            j["target_company"]=True
            j["target_fit"]=t.get("fit")
            break
    if wrong_province(j): continue
    k=dedupe_key(j)
    if k in seen: continue
    seen.add(k)
    s,m,n,c=score_job(j)
    if c=="excluded" or s < 5.0: continue
    j["score"]=s
    j["matched_keywords"]=m
    j["negative_keywords"]=n
    j["fit_category"]=c
    j["key"]=j.get("key") or f'{j.get("source","job")}:{j.get("external_id",k)}'
    out.append(j)

old=load("seen_jobs.json",{})
if isinstance(old,list): old={x:True for x in old}
now=datetime.now(timezone.utc).isoformat()
for j in out:
    j["is_new"]=j["key"] not in old
    j["first_seen"]=now if j["is_new"] else old.get(j["key"],now)
    old[j["key"]]=j["first_seen"]

out.sort(key=lambda x:(not x.get("is_new",False),-x.get("score",0)))
with open("jobs.json","w",encoding="utf-8") as f:
    json.dump({"last_checked":now,"jobs":out},f,ensure_ascii=False,indent=2)
with open("new_jobs.json","w",encoding="utf-8") as f:
    json.dump({"last_checked":now,"jobs":[j for j in out if j["is_new"]]},f,ensure_ascii=False,indent=2)
with open("seen_jobs.json","w",encoding="utf-8") as f:
    json.dump(old,f,ensure_ascii=False,indent=2)
print(f'V4.1 qualified={len(out)}, new={sum(j["is_new"] for j in out)}, strong={sum(j["score"]>=7 for j in out)}')
