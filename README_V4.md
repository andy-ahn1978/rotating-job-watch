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
