"""Aggregate remote-job sources into one client-side-searchable corpus.

Why this exists: Remotive's public API is currently serving a stale CDN-cached
response that *ignores the search query* (verified via the ``age`` response
header — ~11h old, identical job ids for every query). So server-side search is
unreliable. Instead we pull full feeds from several sources, cache the merged
corpus for the process, and filter client-side by the query terms. This makes
the agent's queries meaningful again and is resilient to any single source
degrading — if one feed is down or cached, the others still provide candidates.

Sources (all public, no auth):
- RemoteOK  — primary; English, tech-focused, ~100 jobs/feed.
- Jobicy    — secondary; English, remote-only, ~100 jobs/feed with structured
              industry/level tags.
- Remotive  — tertiary; degraded (see above) but still adds ~32 candidates.
"""

from __future__ import annotations

import re

from . import jobicy, remoteok, remotive
from .remotive import Job

# Process-level cache: the agent re-queries the corpus once per round with a
# different query, so fetch the feeds once and just re-filter.
_corpus: list[Job] | None = None

_STOPWORDS = {
    "remote", "senior", "engineer", "developer", "and", "the", "for", "with",
}


def load_corpus(*, force: bool = False) -> list[Job]:
    """Fetch and merge all sources once, deduplicated. Cached for the process."""
    global _corpus
    if _corpus is not None and not force:
        return _corpus

    jobs: list[Job] = []
    for fetch in (_safe(remoteok.fetch_jobs), _safe(jobicy.fetch_jobs), _safe(_remotive_all)):
        jobs.extend(fetch())

    seen: set[tuple[str, str]] = set()
    deduped: list[Job] = []
    for job in jobs:
        key = (job.title.strip().lower(), job.company.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    _corpus = deduped
    return _corpus


def search(query: str, *, limit: int = 8) -> list[Job]:
    """Return up to `limit` jobs from the corpus most relevant to `query`.

    Ranking: jobs are ordered first by how many distinct query terms hit the
    high-signal fields (title, tags), then by a weighted total that includes
    description hits. Terms match at word starts only ("api" matches "APIs"
    but not "therapist"; "ml" matches "MLOps" but not "html") — plain substring
    matching let generic postings outrank real matches. If nothing matches,
    returns the head of the corpus so the pipeline still produces candidates."""
    corpus = load_corpus()
    terms = [t for t in _terms(query) if t not in _STOPWORDS]
    if not terms:
        return corpus[:limit]
    patterns = [re.compile(rf"(?<![a-z0-9]){re.escape(t)}") for t in terms]

    ranked: list[tuple[int, int, Job]] = []
    for job in corpus:
        title = job.title.lower()
        tags = job.category.lower()
        body = job.description.lower()
        title_hits = sum(1 for p in patterns if p.search(title))
        tag_hits = sum(1 for p in patterns if p.search(tags))
        body_hits = sum(1 for p in patterns if p.search(body))
        strong = title_hits + tag_hits
        score = 3 * title_hits + 2 * tag_hits + body_hits
        if score:
            ranked.append((strong, score, job))

    if not ranked:
        return corpus[:limit]
    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [job for _, _, job in ranked[:limit]]


def _remotive_all() -> list[Job]:
    # Remotive ignores the search param right now, so just pull its feed.
    return remotive.search_jobs(search=None, limit=200)


def _safe(fetch):
    """Wrap a source fetch so one source failing never breaks the corpus."""
    def _run() -> list[Job]:
        try:
            return fetch()
        except Exception:  # noqa: BLE001 - a dead source must not kill the run
            return []
    return _run


def _terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+#.]+", text.lower()) if len(w) >= 3]
