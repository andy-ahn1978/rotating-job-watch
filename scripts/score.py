import re

def _blob(job):
    return " ".join([
        job.get("title",""),
        job.get("company",""),
        job.get("description",""),
        job.get("location",""),
    ]).lower()

def score_job(job, config):
    blob = _blob(job)
    score = 0.0
    matched = []
    negative = []

    for term, value in config.get("positive_terms", {}).items():
        if term.lower() in blob:
            score += float(value)
            matched.append(term)

    for term, value in config.get("negative_terms", {}).items():
        if term.lower() in blob:
            score += float(value)
            negative.append(term)

    # Ontario is a hard preference, not an absolute requirement because some
    # ads say GTA or a city without the word Ontario.
    ontario_places = [
        "ontario","toronto","mississauga","hamilton","burlington","oakville",
        "cambridge","kitchener","guelph","sarnia","sudbury","london","windsor",
        "niagara","stoney creek","brampton","etobicoke"
    ]
    if any(p in blob for p in ontario_places):
        score += 1.0

    # Clamp to a readable 0-10 scale.
    score = max(0.0, min(10.0, round(score, 1)))
    return score, matched, negative
