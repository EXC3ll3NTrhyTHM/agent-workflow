"""Client for the Jobicy public remote-jobs API (no auth required).

https://jobicy.com/api/v2/remote-jobs — returns up to 100 recent remote jobs as
JSON. All postings are remote and English-language, which makes it a strong
complement to RemoteOK (and to Remotive's degraded cached feed). There is a
server-side ``tag`` param, but we pull the full feed and filter client-side
like the other sources (see ``jobs.py``).
"""

from __future__ import annotations

import html

import requests

from .remotive import Job

API_URL = "https://jobicy.com/api/v2/remote-jobs"
_TIMEOUT = 30


def fetch_jobs(limit: int = 100) -> list[Job]:
    """Fetch the recent Jobicy feed as a list of :class:`Job`."""
    resp = requests.get(API_URL, params={"count": min(limit, 100)}, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    jobs: list[Job] = []
    for raw in payload.get("jobs", []):
        if not isinstance(raw, dict) or not raw.get("jobTitle"):
            continue
        jobs.append(_to_job(raw))
        if len(jobs) >= limit:
            break
    return jobs


def _to_job(raw: dict) -> Job:
    try:
        job_id = int(raw.get("id", 0))
    except (TypeError, ValueError):
        job_id = abs(hash(raw.get("jobSlug") or raw.get("url"))) % (10**9)
    # jobIndustry/jobLevel/jobType are lists or strings; merge them into the
    # category field so the client-side filter sees them as tags.
    tags: list[str] = []
    for key in ("jobIndustry", "jobLevel", "jobType"):
        value = raw.get(key)
        if isinstance(value, list):
            tags.extend(str(v) for v in value)
        elif value:
            tags.append(str(value))
    return Job(
        id=job_id,
        title=html.unescape(raw.get("jobTitle", "")),
        company=html.unescape(raw.get("companyName", "")),
        category=html.unescape(", ".join(tags)),
        url=raw.get("url", ""),
        location=raw.get("jobGeo", "") or "Remote",
        description=raw.get("jobDescription", "") or raw.get("jobExcerpt", ""),
    )
