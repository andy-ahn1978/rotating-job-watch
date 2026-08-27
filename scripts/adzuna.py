import os
import requests
from urllib.parse import urlencode

BASE = "https://api.adzuna.com/v1/api/jobs"

def fetch_adzuna_jobs(config):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("Adzuna secrets are not configured; skipping Adzuna.")
        return []

    country = config.get("country", "ca")
    where = config.get("where", "Ontario")
    results_per_page = int(config.get("results_per_page", 50))
    rows = []

    for query in config.get("queries", []):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": results_per_page,
            "what": query,
            "where": where,
            "content-type": "application/json",
            "sort_by": "date",
        }
        url = f"{BASE}/{country}/search/1"
        try:
            r = requests.get(url, params=params, timeout=30, headers={"Accept":"application/json"})
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"Adzuna ERROR [{query}]: {e}")
            continue

        for x in data.get("results", []):
            company = (x.get("company") or {}).get("display_name") or "Unknown company"
            loc = (x.get("location") or {}).get("display_name") or where
            rows.append({
                "external_id": str(x.get("id") or ""),
                "company": company,
                "title": x.get("title") or "",
                "location": loc,
                "description": x.get("description") or "",
                "url": x.get("redirect_url") or "",
                "created": x.get("created"),
                "salary_min": x.get("salary_min"),
                "salary_max": x.get("salary_max"),
                "source": "Adzuna",
                "search_query": query,
            })
        print(f"Adzuna [{query}]: {len(data.get('results', []))} results")

    return rows
