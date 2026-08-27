import requests


def fetch_official_jobs(targets):
    """
    Fetch jobs from explicitly configured official career URLs.

    Most targets are currently monitored through Adzuna.
    A target without careers_url is simply skipped instead of causing an error.
    """
    jobs = []

    for target in targets:
        careers_url = target.get("careers_url")
        if not careers_url:
            continue

        name = target.get("name", "Unknown")

        try:
            # This keeps backward compatibility with the current simple official
            # source setup. Company-specific parsing can be added later.
            response = requests.get(
                careers_url,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; RotatingJobWatch/4.0; "
                        "+personal-job-monitor)"
                    )
                },
            )
            response.raise_for_status()

            # The previous V4 implementation only had a special official parser
            # for Comairco. Without a known parser, do not invent job entries.
            # We still verify that the configured careers URL is reachable.
            print(
                f"Official [{name}]: careers page reachable "
                f"({response.status_code}); no generic parser configured"
            )

        except Exception as exc:
            print(f"Official [{name}] ERROR: {exc}")

    return jobs
