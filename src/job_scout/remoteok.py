"""Client for the RemoteOK public jobs feed (no auth required).

https://remoteok.com/api — returns the full recent feed as a JSON array. The
first element is a metadata/legal object (no ``position``) and is skipped. There
is no server-side search param, so callers filter client-side (see ``jobs.py``).
"""

from __future__ import annotations

import html

import requests

from .remotive import Job

API_URL = "https://remoteok.com/api"
_TIMEOUT = 30
# RemoteOK blocks the default requests UA; a browser-ish UA is required.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; job-scout/0.1)"}


def fetch_jobs(limit: int = 200) -> list[Job]:
    """Fetch the recent RemoteOK feed as a list of :class:`Job`."""
    resp = requests.get(API_URL, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    jobs: list[Job] = []
    for raw in payload:
        if not isinstance(raw, dict) or not raw.get("position"):
            continue  # skip the leading metadata/legal element
        jobs.append(_to_job(raw))
        if len(jobs) >= limit:
            break
    return jobs


def _to_job(raw: dict) -> Job:
    try:
        job_id = int(raw.get("id", 0))
    except (TypeError, ValueError):
        job_id = abs(hash(raw.get("slug") or raw.get("url"))) % (10**9)
    tags = raw.get("tags") or []
    return Job(
        id=job_id,
        title=html.unescape(raw.get("position", "")),
        company=html.unescape(raw.get("company", "")),
        category=", ".join(tags),
        url=raw.get("url", "") or raw.get("apply_url", ""),
        location=raw.get("location", "") or "Remote",
        description=raw.get("description", ""),
    )
