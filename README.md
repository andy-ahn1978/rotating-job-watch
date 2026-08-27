# V4.1.1 compatibility fix

Replace BOTH files together:

- scripts/score.py
- scripts/monitor.py

Why:
The prior patch mixed the old V4 monitor interface with the new scoring function.
This fixed pair is compatible with the existing V4:
- scripts/adzuna.py -> fetch_adzuna_jobs()
- scripts/official.py -> fetch_official_jobs()

Expected log:
V4.1.1 raw=...
V4.1.1 qualified=..., new=..., strong=...

The line `Official [Comairco]: 1 results` only means Comairco's official-site parser found one posting.
It does NOT mean the whole system found only one job.


# Rotating Job Watch v4.1 patch

Replace:
- scripts/score.py
- scripts/monitor.py
- scripts/notify.py

No workflow change is required if v4 already runs `python scripts/monitor.py` and then `python scripts/notify.py`.

Changes:
- Sales-first filtering
- Excludes Millwright/Journeyman/Mechanic/Technician noise unless title is explicitly sales/commercial
- Better duplicate detection
- Filters obvious wrong-province mappings in descriptions
- Fit category: strong >=7, match >=5
- Telegram alert sends only newly detected qualified jobs

Telegram GitHub repository secrets:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID


# Rotating Job Watch v4 patch

Upgrade the EXISTING `rotating-job-watch` repository. Do not create a new repository.

## Replace
- `targets.json`
- `app.js`
- `scripts/monitor.py`
- `scripts/notify.py`
- `.github/workflows/job-watch.yml`
- `requirements.txt`

## Add
- `search_config.json`
- `scripts/adzuna.py`
- `scripts/official.py`
- `scripts/score.py`

## Optional CSS addition
Append the contents of `styles_v4_additions.css` to the bottom of the existing `styles.css`.

## Adzuna credentials
Register at https://developer.adzuna.com/ and obtain:
- App ID
- App Key

GitHub repository:
Settings -> Secrets and variables -> Actions -> New repository secret

Create:
- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`

Never put the real key inside source code or targets.json.

## First V4 run
After replacing files and adding the secrets:

Actions -> Job Watch V4 -> Run workflow

The first V4 run uses the existing seen history where possible. If you want a completely fresh baseline with no flood of NEW alerts, edit `seen_jobs.json` to:
{
  "initialized": false,
  "ids": []
}

Then run V4 once. Existing jobs become the baseline and later unseen jobs generate alerts.

## Sources
- Adzuna: automatic Ontario-wide job discovery via official API.
- Official Careers: currently Comairco parser retained.
- LinkedIn: search links only, not scraped.
- Indeed: search links only, not scraped.
- Job Bank: search links only, not scraped.

## Scoring
Edit `search_config.json` to change:
- query terms
- positive weights
- negative weights
- minimum score
- strong-match threshold


# Rotating Job Watch v3

V3 combines:

1. Official Careers monitoring
2. LinkedIn Jobs search links
3. Indeed search links
4. Mobile-first job view
5. Company-level application counts
6. GitHub Issue alerts for newly detected official postings
7. Optional Telegram alerts

## Core behavior

GitHub Actions checks official company sites twice per day.
When a matching job link appears for the first time, it is:
- added to `jobs.json`
- marked NEW in the app
- sent as a GitHub Issue alert
- optionally sent by Telegram

LinkedIn and Indeed are intentionally NOT scraped.
Each company instead has direct search buttons that open current search results on those services.

This is more reliable than trying to bypass login, JavaScript rendering, or anti-bot controls.

## Deploy

1. Create a GitHub repository.
2. Upload all files and folders, including `.github`.
3. Enable GitHub Pages from the main branch root.
4. Open the Pages URL on your phone.
5. Add to Home Screen.
6. Install GitHub mobile and enable notifications if you want issue-based push alerts.

## Notes

Some career platforms such as Workday, SuccessFactors, or other JavaScript-heavy systems may not expose real job links in raw HTML.
Those targets may need a dedicated adapter later.
V3 is structured so company-specific parsers can be added without changing the app UI.
