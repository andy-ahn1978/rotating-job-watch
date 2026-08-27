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
