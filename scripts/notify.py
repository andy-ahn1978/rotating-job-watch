#!/usr/bin/env python3
import json, os, requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
new=json.loads((ROOT/"new_jobs.json").read_text()) if (ROOT/"new_jobs.json").exists() else []
if not new:
 print("No new jobs."); raise SystemExit(0)
body="\n".join([f"- **{j['company']}** — [{j['title']}]({j['url']}) — {j.get('location','')}" for j in new[:20]])
token=os.getenv("GITHUB_TOKEN"); repo=os.getenv("GITHUB_REPOSITORY")
if token and repo:
 r=requests.post(f"https://api.github.com/repos/{repo}/issues",
   headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},
   json={"title":f"New target jobs: {len(new)}","body":body},timeout=20)
 print("GitHub alert",r.status_code)
tg=os.getenv("TELEGRAM_BOT_TOKEN"); chat=os.getenv("TELEGRAM_CHAT_ID")
if tg and chat:
 text="New target jobs:\n"+"\n".join([f"{j['company']} — {j['title']}\n{j['url']}" for j in new[:10]])
 requests.post(f"https://api.telegram.org/bot{tg}/sendMessage",json={"chat_id":chat,"text":text},timeout=20)
 print("Telegram alert sent")
