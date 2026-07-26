"""Client for the We Work Remotely public RSS feeds (no auth required).

https://weworkremotely.com/remote-jobs.rss — the main feed carries the ~100
most recent postings across all categories; each category also has its own
feed with deeper coverage. Pulling the main feed plus every category feed and
deduplicating yields ~400-500 unique postings — added in Week 7 because the
evaluation showed corpus supply was the binding constraint (10/12 test cases
had fewer than 3 relevant postings in the old 241-posting corpus).

Items look like ``<title>Company: Job Title</title>`` with ``region``,
``category``, ``type`` and ``skills`` fields; there is no numeric id, so a
stable one is derived from the posting URL (see ``ids.py``).
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

import requests

from .ids import stable_id
from .remotive import Job

BASE = "https://weworkremotely.com"
MAIN_FEED = f"{BASE}/remote-jobs.rss"
# Category slugs verified live 2026-07-25; a missing/renamed category just
# contributes zero items (each feed is fetched independently).
CATEGORY_FEEDS = [
    f"{BASE}/categories/{slug}.rss"
    for slug in (
        "remote-programming-jobs",
        "remote-devops-sysadmin-jobs",
        "remote-product-jobs",
        "remote-design-jobs",
        "remote-sales-and-marketing-jobs",
        "remote-management-and-finance-jobs",
        "remote-customer-support-jobs",
    )
]
_TIMEOUT = 30
# WWR blocks the default requests UA; a browser-ish UA is required.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; job-scout/0.1)"}


def fetch_jobs(limit: int = 600) -> list[Job]:
    """Fetch the main WWR feed plus all category feeds, deduplicated by URL."""
    jobs: list[Job] = []
    seen_urls: set[str] = set()
    for feed_url in [MAIN_FEED, *CATEGORY_FEEDS]:
        for job in _fetch_feed(feed_url):
            if job.url in seen_urls:
                continue
            seen_urls.add(job.url)
            jobs.append(job)
            if len(jobs) >= limit:
                return jobs
    return jobs


def _fetch_feed(feed_url: str) -> list[Job]:
    """Fetch one RSS feed; a failing feed contributes zero items, not an error."""
    try:
        resp = requests.get(feed_url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception:  # noqa: BLE001 - one dead feed must not kill the source
        return []
    return [job for item in root.iter("item") if (job := _to_job(item))]


def _to_job(item: ET.Element) -> Job | None:
    def text(tag: str) -> str:
        el = item.find(tag)
        return (el.text or "").strip() if el is not None else ""

    raw_title = html.unescape(text("title"))
    url = text("link") or text("guid")
    if not raw_title or not url:
        return None
    # Titles are "Company: Job Title"; keep both halves if the colon is missing.
    company, _, title = raw_title.partition(": ")
    if not title:
        company, title = "", raw_title
    tags = ", ".join(t for t in (text("category"), text("type"), text("skills")) if t)
    description = re.sub(r"<img[^>]*>", " ", text("description"))
    return Job(
        id=stable_id(url),
        title=title,
        company=company,
        category=tags,
        url=url,
        location=text("region") or "Remote",
        description=description,
    )
