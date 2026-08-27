import json, os, urllib.request, urllib.parse

def load_jobs():
    try:
        with open("new_jobs.json", encoding="utf-8") as f:
            return json.load(f).get("jobs",[])
    except Exception:
        return []

jobs=load_jobs()
if not jobs:
    print("No new jobs; no Telegram alert.")
    raise SystemExit(0)

token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
chat=os.getenv("TELEGRAM_CHAT_ID","").strip()
if not token or not chat:
    print("Telegram secrets not configured; skipping alert.")
    raise SystemExit(0)

top=sorted(jobs,key=lambda x:x.get("score",0),reverse=True)[:10]
lines=[f"Rotating Job Watch: {len(jobs)} new matching job(s)"]
for j in top:
    lines += ["", f'[{j.get("score",0)}/10] {j.get("title","")}',
              f'{j.get("company","")} | {j.get("location","")}', j.get("url","")]
if len(jobs)>10: lines += ["",f"+ {len(jobs)-10} more in the app"]
text="\n".join(lines)[:4000]

url=f"https://api.telegram.org/bot{token}/sendMessage"
data=urllib.parse.urlencode({"chat_id":chat,"text":text,"disable_web_page_preview":"true"}).encode()
with urllib.request.urlopen(url,data=data,timeout=20) as r:
    print("Telegram:",r.status)
