"""The Job Scout agent loop.

A deliberately small but genuine agent: it *perceives* (search + score), *acts*
(decide which postings are alert-worthy), *remembers* (the queries it has already
tried), and *self-corrects* (derives a fresh query and goes again when a round
returns too few good matches). It stops when it has enough good matches or runs
out of rounds.

    derive query ─▶ search ─▶ score ─▶ enough good matches? ──yes─▶ done
         ▲                                   │
         └──────── refine (avoid repeats) ◀──no

Kept as a plain Python loop rather than a LangGraph graph for the baseline — the
control flow is linear and this is far easier to run and reason about. Porting
the same nodes to LangGraph is a later-week refinement, not a Week 3 need.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import db, tools
from .tools import ScoredJob


@dataclass
class RoundLog:
    query: str
    n_jobs: int
    n_good: int
    scorer: str  # "claude" or "fallback" — which path scored this round
    job_ids: list[int] = field(default_factory=list)  # postings this round surfaced


@dataclass
class AgentResult:
    resume_label: str
    scored: list[ScoredJob]              # every posting seen, best first
    alerts: list[ScoredJob]              # postings at/above the alert threshold
    tried_queries: list[str]
    rounds: list[RoundLog] = field(default_factory=list)

    @property
    def top(self) -> list[ScoredJob]:
        return self.scored


def run_agent(
    resume_text: str,
    *,
    resume_label: str = "résumé",
    db_path: str | None = None,
    alert_threshold: float = 8.0,
    good_threshold: float = 7.0,
    target_good: int = 3,
    max_rounds: int = 3,
    jobs_per_round: int = 8,
    claude_path: str | None = None,
    home: str | None = None,
    model: str | None = None,
    verbose: bool = False,
) -> AgentResult:
    """Run the search→score→decide→refine loop for a single résumé.

    `good_threshold` is the bar for "worth surfacing"; `target_good` is how many
    such matches end the search early. `alert_threshold` is the (higher) bar an
    email alert would use. Persistence is optional — pass `db_path` to record the
    ranked jobs and tried queries to SQLite (so daily runs don't repeat work).
    `verbose` streams progress to stdout — the Claude calls take tens of seconds
    each, so an interactive run is silent for minutes without it."""

    say = (lambda *a: print(*a, flush=True)) if verbose else (lambda *a: None)
    seen: dict[int, ScoredJob] = {}
    tried: set[str] = set()
    rounds: list[RoundLog] = []

    conn_cm = db.connect(db_path) if db_path else None
    conn = conn_cm.__enter__() if conn_cm else None
    try:
        say("deriving a search query from the résumé (Claude, ~10-30s)...")
        query = tools.derive_query(
            resume_text, tried=tried, claude_path=claude_path, home=home, model=model
        )
        for round_no in range(1, max_rounds + 1):
            query_key = query.strip().lower()
            if query_key in tried:  # agent's memory: never repeat a query
                say(f"  {query!r} was already tried — deriving another (Claude, ~10-30s)...")
                query = tools.derive_query(
                    resume_text, tried=tried, claude_path=claude_path,
                    home=home, model=model,
                )
                query_key = query.strip().lower()
                if query_key in tried:
                    break  # nothing new to try
            tried.add(query_key)
            if conn is not None:
                db.record_query(conn, query)

            say(f"round {round_no}/{max_rounds}: searching the job corpus for {query!r}...")
            jobs = tools.search_jobs(query, limit=jobs_per_round)
            say(f"  {len(jobs)} candidates — scoring against the résumé (Claude, ~30-60s)...")
            scored = tools.score_jobs(
                resume_text, jobs, claude_path=claude_path, home=home, model=model
            )
            for s in scored:
                # Keep the better score if we have seen this posting before.
                if s.job.id not in seen or s.score > seen[s.job.id].score:
                    seen[s.job.id] = s
                if conn is not None:
                    db.upsert_job(
                        conn, job_id=s.job.id, title=s.job.title,
                        company=s.job.company, url=s.job.url,
                        score=s.score, reasoning=s.reasoning,
                    )

            n_good = sum(1 for s in seen.values() if s.score >= good_threshold)
            scorer = scored[0].source if scored else "fallback"
            rounds.append(RoundLog(query, len(jobs), n_good, scorer,
                                   [j.id for j in jobs]))
            best = max((s.score for s in seen.values()), default=0.0)
            say(f"  scored [{scorer}]: {n_good} good match(es) >= {good_threshold} "
                f"so far (best {best:.1f})")

            if n_good >= target_good:
                say(f"  target of {target_good} good matches reached — stopping early")
                break  # enough good matches — stop early

            # Self-correct: derive a different query for the next round. Skipped
            # on the last round — the eval harness caught that deriving here too
            # burned one Claude call per full-length run whose result was never
            # used (docs/evaluation.md, step efficiency).
            if round_no < max_rounds:
                say("  not enough good matches — deriving a fresh query (Claude, ~10-30s)...")
                query = tools.derive_query(
                    resume_text, tried=tried, claude_path=claude_path,
                    home=home, model=model,
                )
    finally:
        if conn_cm is not None:
            conn_cm.__exit__(None, None, None)

    ranked = sorted(seen.values(), key=lambda s: s.score, reverse=True)
    alerts = [s for s in ranked if s.score >= alert_threshold]
    return AgentResult(
        resume_label=resume_label,
        scored=ranked,
        alerts=alerts,
        tried_queries=sorted(tried),
        rounds=rounds,
    )
