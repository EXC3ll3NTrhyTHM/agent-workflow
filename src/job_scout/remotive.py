"""Client for the Remotive public jobs API (no auth required).

https://remotive.com/api/remote-jobs
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

API_URL = "https://remotive.com/api/remote-jobs"
_TIMEOUT = 30


@dataclass(frozen=True)
class Job:
    id: int
    title: str
    company: str
    category: str
    url: str
    location: str
    description: str

    @classmethod
    def from_api(cls, raw: dict) -> "Job":
        return cls(
            id=raw["id"],
            title=raw.get("title", ""),
            company=raw.get("company_name", ""),
            category=raw.get("category", ""),
            url=raw.get("url", ""),
            location=raw.get("candidate_required_location", ""),
            description=raw.get("description", ""),
        )


def search_jobs(search: str | None = None, limit: int = 50) -> list[Job]:
    """Fetch jobs from Remotive, optionally filtered by a free-text search.

    Remotive supports `search` and `category` query params and a `limit`.
    """
    params: dict[str, str | int] = {"limit": limit}
    if search:
        params["search"] = search

    resp = requests.get(API_URL, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    return [Job.from_api(j) for j in payload.get("jobs", [])]
