import os
import re
import time
import requests
from pathlib import Path

BASE = "https://api.adzuna.com/v1/api/jobs"
ROOT = Path(__file__).resolve().parents[1]


def _norm_company(value):
    value = (value or "").lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(
        r"\b(inc|incorporated|ltd|limited|corp|corporation|company|co|canada|canadian|llc|lp)\b",
        " ",
        value,
    )
    return re.sub(r"\s+", " ", value).strip()


def _company_matches(result_company, target):
    actual = _norm_company(result_company)
    if not actual:
        return False

    aliases = [target.get("name", "")]
    aliases.extend(re.split(r"[|/]", target.get("name", "")))
    aliases.extend(target.get("aliases", []))

    for alias in aliases:
        candidate = _norm_company(alias)
        if len(candidate) < 4:
            continue
        if actual == candidate or actual in candidate or candidate in actual:
            return True

    return False


def _make_job(x, where, search_query, search_type="keyword", target=None):
    company = (x.get("company") or {}).get("display_name") or "Unknown company"
    location = (x.get("location") or {}).get("display_name") or where

    return {
        "external_id": str(x.get("id") or ""),
        "company": company,
        "title": x.get("title") or "",
        "location": location,
        "description": x.get("description") or "",
        "url": x.get("redirect_url") or "",
        "created": x.get("created"),
        "salary_min": x.get("salary_min"),
        "salary_max": x.get("salary_max"),
        "source": "Adzuna",
        "search_query": search_query,
        "search_type": search_type,
        "searched_target": target.get("name") if target else None,
    }


def _request_jobs(app_id, app_key, country, where, query, results_per_page):
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
    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def _load_targets():
    import json

    path = ROOT / "targets.json"
    if not path.exists():
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Targets ERROR: {exc}")
        return []


def fetch_adzuna_jobs(config):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        print("Adzuna secrets are not configured; skipping Adzuna.")
        return []

    country = config.get("country", "ca")
    where = config.get("where", "Ontario")
    results_per_page = int(config.get("results_per_page", 50))
    target_results_per_company = int(config.get("target_results_per_company", 20))

    # Default Adzuna rate limit is commonly 25 requests/minute.
    # 2.6 sec spacing keeps this run below that level.
    request_delay = float(config.get("adzuna_request_delay_seconds", 2.6))

    rows = []
    last_request_at = 0.0

    def run_query(query, result_limit):
        nonlocal last_request_at

        elapsed = time.time() - last_request_at
        if last_request_at and elapsed < request_delay:
            time.sleep(request_delay - elapsed)

        try:
            data = _request_jobs(
                app_id,
                app_key,
                country,
                where,
                query,
                result_limit,
            )
            last_request_at = time.time()
            return data.get("results", [])
        except Exception as exc:
            last_request_at = time.time()
            print(f"Adzuna ERROR [{query}]: {exc}")
            return []

    # 1. Broad Ontario keyword searches.
    queries = config.get("queries", [])
    for query in queries:
        results = run_query(query, results_per_page)

        for item in results:
            rows.append(
                _make_job(
                    item,
                    where,
                    query,
                    search_type="keyword",
                )
            )

        print(f"Adzuna keyword [{query}]: {len(results)} results")

    # 2. Search EVERY monitored target company once per workflow run.
    targets = [
        target for target in _load_targets()
        if target.get("monitor", True) and target.get("name")
    ]

    print(f"Adzuna target-company scan: {len(targets)} targets")

    matched_target_ads = 0

    for number, target in enumerate(targets, start=1):
        target_name = target["name"].strip()
        results = run_query(target_name, target_results_per_company)

        matched = 0
        for item in results:
            employer = (item.get("company") or {}).get("display_name") or ""

            # Adzuna's "what" field may find a company mentioned only in ad text.
            # Only keep results where the actual listed employer matches our target.
            if not _company_matches(employer, target):
                continue

            rows.append(
                _make_job(
                    item,
                    where,
                    target_name,
                    search_type="target_company",
                    target=target,
                )
            )
            matched += 1
            matched_target_ads += 1

        print(
            f"Adzuna target [{number}/{len(targets)}] [{target_name}]: "
            f"{matched} employer-matched / {len(results)} search results"
        )

    print(
        f"Adzuna scan complete: "
        f"{len(queries)} keyword queries + {len(targets)} target companies; "
        f"{matched_target_ads} target-company ads matched"
    )

    return rows
