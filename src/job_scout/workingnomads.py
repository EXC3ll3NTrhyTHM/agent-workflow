"""Client for the Working Nomads public jobs API (no auth required).

https://www.workingnomads.com/api/exposed_jobs/ — returns the ~40 most recent
postings as a JSON array. Small, but it covers non-engineering categories
(consulting, marketing, writing) thinner in the other feeds — added in Week 7
as part of widening corpus supply. Postings carry no explicit id; the numeric
segment of the job URL is used when present, else a stable digest (``ids.py``).
"""

from __future__ import annotations

import html
import re

import requests

from .ids import stable_id
from .remotive import Job

API_URL = "https://www.workingnomads.com/api/exposed_jobs/"
_TIMEOUT = 30


def fetch_jobs(limit: int = 100) -> list[Job]:
    """Fetch the recent Working Nomads feed as a list of :class:`Job`."""
    resp = requests.get(API_URL, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    jobs: list[Job] = []
    for raw in payload:
        if not isinstance(raw, dict) or not raw.get("title") or not raw.get("url"):
            continue
        jobs.append(_to_job(raw))
        if len(jobs) >= limit:
            break
    return jobs


def _to_job(raw: dict) -> Job:
    url = raw["url"]
    id_match = re.search(r"/job/\w+/(\d+)", url)
    tags = ", ".join(
        t for t in (raw.get("category_name", ""), raw.get("tags", "")) if t
    )
    return Job(
        id=int(id_match.group(1)) if id_match else stable_id(url),
        title=html.unescape(raw["title"]),
        company=html.unescape(raw.get("company_name", "")),
        category=tags,
        url=url,
        location=raw.get("location", "") or "Remote",
        description=raw.get("description", ""),
    )
