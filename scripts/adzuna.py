import os
import re
import time
import math
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


def _company_matches(result_company, target_name):
    a = _norm_company(result_company)
    b = _norm_company(target_name)

    if not a or not b:
        return False

    if a == b or a in b or b in a:
        return True

    # Handle names such as "DXP | NATPRO", while avoiding very short/generic tokens.
    target_parts = [
        p.strip()
        for p in re.split(r"[|/]", target_name or "")
        if len(_norm_company(p.strip())) >= 4
    ]
    for part in target_parts:
        p = _norm_company(part)
        if p and (p == a or p in a or a in p):
            return True

    return False


def _make_job(x, where, search_query, search_type="keyword", target=None):
    company = (x.get("company") or {}).get("display_name") or "Unknown company"
    loc = (x.get("location") or {}).get("display_name") or where

    return {
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
    r = requests.get(
        url,
        params=params,
        timeout=30,
        headers={"Accept": "application/json"},
    )
    r.raise_for_status()
    return r.json()


def _load_targets():
    path = ROOT / "targets.json"
    if not path.exists():
        return []
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Targets ERROR: {e}")
        return []


def _target_batch(targets, batch_size):
    """
    Rotate target-company searches by 12-hour UTC slots.
    No cursor/state file is required, so GitHub Actions can remain unchanged.
    """
    targets = [t for t in targets if t.get("monitor", True) and t.get("name")]
    if not targets:
        return [], 0, 0

    batch_size = max(1, min(int(batch_size), len(targets)))
    batch_count = math.ceil(len(targets) / batch_size)

    slot = int(time.time() // (12 * 60 * 60))
    batch_index = slot % batch_count

    start = batch_index * batch_size
    end = min(start + batch_size, len(targets))
    return targets[start:end], batch_index + 1, batch_count


def fetch_adzuna_jobs(config):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        print("Adzuna secrets are not configured; skipping Adzuna.")
        return []

    country = config.get("country", "ca")
    where = config.get("where", "Ontario")
    results_per_page = int(config.get("results_per_page", 50))

    # Keep safely below Adzuna's default 25 hits/minute limit.
    request_delay = float(config.get("adzuna_request_delay_seconds", 2.6))

    rows = []
    last_request_at = 0.0

    def run_query(query, result_limit, search_type="keyword", target=None):
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
        except Exception as e:
            last_request_at = time.time()
            label = target.get("name") if target else query
            print(f"Adzuna ERROR [{label}]: {e}")
            return []

        results = data.get("results", [])
        return results

    # 1) Broad keyword search across Ontario.
    for query in config.get("queries", []):
        results = run_query(
            query,
            results_per_page,
            search_type="keyword",
        )

        for x in results:
            rows.append(
                _make_job(
                    x,
                    where,
                    query,
                    search_type="keyword",
                )
            )

        print(f"Adzuna keyword [{query}]: {len(results)} results")

    # 2) Direct target-company search.
    targets = _load_targets()
    target_batch_size = int(config.get("target_batch_size", 35))
    target_results_per_company = int(config.get("target_results_per_company", 20))

    selected, batch_no, batch_count = _target_batch(targets, target_batch_size)

    if selected:
        print(
            f"Adzuna target-company batch {batch_no}/{batch_count}: "
            f"{len(selected)} of {len([t for t in targets if t.get('monitor', True)])} targets"
        )

    for target in selected:
        target_name = target.get("name", "").strip()
        if not target_name:
            continue

        results = run_query(
            target_name,
            target_results_per_company,
            search_type="target_company",
            target=target,
        )

        matched = 0
        for x in results:
            result_company = (x.get("company") or {}).get("display_name") or ""

            # Company-name searches can match a company mentioned only in the ad text.
            # Keep only ads whose employer actually matches the target.
            if not _company_matches(result_company, target_name):
                continue

            rows.append(
                _make_job(
                    x,
                    where,
                    target_name,
                    search_type="target_company",
                    target=target,
                )
            )
            matched += 1

        print(
            f"Adzuna target [{target_name}]: "
            f"{matched} employer-matched / {len(results)} search results"
        )

    return rows
