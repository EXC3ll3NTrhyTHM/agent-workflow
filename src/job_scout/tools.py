"""The agent's tools — the discrete actions the agent loop can take.

Each tool is a plain function so the loop (``agent.py``) reads as a sequence of
deliberate actions: *search* the web, *score* postings against the résumé, and
*derive* a fresh search query when results are thin.

Two of the tools (`score_jobs`, `derive_query`) call Claude. To honour the Week 3
"it runs" bar even when Claude is rate-limited or absent, each has a
deterministic, clearly-labelled fallback (keyword overlap / a keyword pulled
from the résumé). The fallback never silently masquerades as the model — every
result carries a `source` of ``"claude"`` or ``"fallback"`` so the report is
honest about which path ran.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import claude_cli
from .remotive import Job, search_jobs as _remotive_search

# Words too generic to make a useful job-board query or overlap signal.
_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "was", "this",
    "that", "from", "have", "has", "will", "all", "can", "out", "use", "using",
    "work", "team", "role", "years", "year", "experience", "strong", "build",
    "building", "including", "across", "into", "skills", "ability", "etc",
}


# --------------------------------------------------------------------------- #
# Tool 1: search the web for jobs (Remotive — public, no auth).
# --------------------------------------------------------------------------- #
def search_jobs(query: str, *, limit: int = 8) -> list[Job]:
    """Search Remotive for postings matching `query`. Thin wrapper for symmetry
    with the other tools and so the agent loop has one obvious call site.

    Remotive's own `limit` param is unreliable for `search` queries (it can return
    far more), so we hard-cap the list here to keep the scoring prompt bounded."""
    return _remotive_search(search=query, limit=limit)[:limit]


# --------------------------------------------------------------------------- #
# Tool 2: score postings against the résumé (Claude, with a fallback).
# --------------------------------------------------------------------------- #
@dataclass
class ScoredJob:
    job: Job
    score: float          # 0-10 match against the résumé
    reasoning: str
    source: str           # "claude" or "fallback"


def score_jobs(
    resume_text: str,
    jobs: list[Job],
    *,
    claude_path: str | None = None,
    home: str | None = None,
    model: str | None = None,
    desc_chars: int = 600,
) -> list[ScoredJob]:
    """Score every posting against the résumé in a single Claude call.

    Batching all postings into one prompt keeps the run fast and cheap and means
    the model sees them side-by-side. Falls back to keyword overlap if Claude is
    unavailable so the pipeline still produces output.
    """
    if not jobs:
        return []

    prompt = _build_scoring_prompt(resume_text, jobs, desc_chars=desc_chars)
    try:
        raw = claude_cli.run_claude(
            prompt, claude_path=claude_path, home=home, model=model, timeout=180
        )
        parsed = claude_cli.extract_json(raw)
        return _scores_from_payload(parsed, jobs)
    except (claude_cli.ClaudeError, ValueError, KeyError):
        # Rate-limited, not logged in, or unparseable output — degrade gracefully.
        return [_fallback_score(resume_text, job) for job in jobs]


def _build_scoring_prompt(resume_text: str, jobs: list[Job], *, desc_chars: int) -> str:
    blocks = []
    for job in jobs:
        desc = re.sub(r"<[^>]+>", " ", job.description)  # strip Remotive's HTML
        desc = re.sub(r"\s+", " ", desc).strip()[:desc_chars]
        blocks.append(
            f"### JOB id={job.id}\n"
            f"Title: {job.title}\nCompany: {job.company}\n"
            f"Location: {job.location}\nDescription: {desc}"
        )
    jobs_block = "\n\n".join(blocks)
    return (
        "You are a job-matching assistant. Score how well each job posting "
        "matches the candidate's résumé, from 0 (no fit) to 10 (excellent fit). "
        "Judge on skills, seniority, and domain overlap.\n\n"
        "Respond with ONLY a JSON object, no prose and no markdown fences, in "
        'exactly this shape:\n'
        '{"scores": [{"id": <job id>, "score": <0-10>, '
        '"reasoning": "<one short sentence>"}]}\n\n'
        f"=== RÉSUMÉ ===\n{resume_text.strip()}\n\n"
        f"=== JOBS ===\n{jobs_block}\n"
    )


def _scores_from_payload(payload: dict, jobs: list[Job]) -> list[ScoredJob]:
    by_id = {job.id: job for job in jobs}
    scored: dict[int, ScoredJob] = {}
    for entry in payload.get("scores", []):
        try:
            job_id = int(entry["id"])
        except (KeyError, TypeError, ValueError):
            continue
        job = by_id.get(job_id)
        if job is None:
            continue
        score = max(0.0, min(10.0, float(entry.get("score", 0))))
        scored[job_id] = ScoredJob(
            job=job,
            score=score,
            reasoning=str(entry.get("reasoning", "")).strip(),
            source="claude",
        )
    # Any posting the model omitted still gets a (fallback) row so nothing vanishes.
    for job in jobs:
        scored.setdefault(job.id, _fallback_score("", job))
    return [scored[job.id] for job in jobs]


def _fallback_score(resume_text: str, job: Job) -> ScoredJob:
    """Keyword-overlap score used when Claude is unavailable. Crude on purpose —
    it exists so the pipeline always produces a number, not to be accurate."""
    resume_terms = _keywords(resume_text)
    job_terms = _keywords(f"{job.title} {job.category} {job.description}")
    if not resume_terms or not job_terms:
        return ScoredJob(job, 0.0, "fallback: no overlap signal", "fallback")
    overlap = len(resume_terms & job_terms)
    score = min(10.0, round(overlap / max(4, len(resume_terms) * 0.15), 1))
    return ScoredJob(
        job, score, f"fallback: {overlap} overlapping keyword(s)", "fallback"
    )


# --------------------------------------------------------------------------- #
# Tool 3: derive / refine a search query from the résumé (Claude, with fallback).
# --------------------------------------------------------------------------- #
def derive_query(
    resume_text: str,
    *,
    tried: set[str] | None = None,
    claude_path: str | None = None,
    home: str | None = None,
    model: str | None = None,
) -> str:
    """Ask Claude for a short job-board search query implied by the résumé that
    has not been tried yet. Falls back to the résumé's most distinctive keywords."""
    tried = tried or set()
    prompt = (
        "From the résumé below, output ONE short job-board search query (2-4 "
        "words, role + a key skill) likely to surface relevant remote jobs. "
        f"Do NOT reuse any of these already-tried queries: {sorted(tried)}.\n"
        'Respond with ONLY JSON: {"query": "<query>"}\n\n'
        f"=== RÉSUMÉ ===\n{resume_text.strip()}\n"
    )
    try:
        raw = claude_cli.run_claude(
            prompt, claude_path=claude_path, home=home, model=model, timeout=120
        )
        query = str(claude_cli.extract_json(raw).get("query", "")).strip()
        if query and query.lower() not in tried:
            return query
    except (claude_cli.ClaudeError, ValueError, KeyError):
        pass
    return _fallback_query(resume_text, tried)


def _fallback_query(resume_text: str, tried: set[str]) -> str:
    """Pick the most frequent distinctive résumé keywords not yet tried."""
    freq: dict[str, int] = {}
    for word in _tokens(resume_text):
        if word in _STOPWORDS or len(word) < 4:
            continue
        freq[word] = freq.get(word, 0) + 1
    ranked = sorted(freq, key=lambda w: freq[w], reverse=True)
    for i in range(0, len(ranked), 2):
        candidate = " ".join(ranked[i : i + 2])
        if candidate and candidate.lower() not in tried:
            return candidate
    return (ranked[0] if ranked else "software")


# --------------------------------------------------------------------------- #
# Small text helpers.
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z+#.]+", text.lower())


def _keywords(text: str) -> set[str]:
    return {w for w in _tokens(text) if len(w) >= 4 and w not in _STOPWORDS}
