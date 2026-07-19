"""Week 6 evaluation: relevance judging and metric computation.

The agent's own scorer cannot grade the agent — that would be the system marking
its own homework. So evaluation uses a *separate* instrument: each test case in
``tests/eval_cases.json`` carries an explicit relevance rubric (what counts as a
relevant posting for this résumé, and what near-misses do not), and an LLM judge
applies that rubric as a binary relevant/not-relevant call per posting, with a
failure category for the misses. The judge prompt shares no text with the
scoring prompt in ``tools.py``.

Metrics (Track 3 guidance: task success rate, step efficiency, error recovery):
- task success   — ≥3 of the agent's top-5 postings judged relevant.
- precision@5    — judged-relevant fraction of the top 5.
- step efficiency— rounds used out of the allowed max, and early-stop rate.
- error recovery — of runs where round 1 alone would have failed the task,
                   how many the refinement loop rescued.

Everything here except :func:`judge_jobs` is pure and offline-testable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import claude_cli
from .remotive import Job

# Failure taxonomy the judge picks from for non-relevant postings. Kept short on
# purpose — categories only earn a slot once they describe a repeatable mistake.
CATEGORIES = (
    "wrong-role-family",   # different job family entirely (analyst vs writer)
    "adjacent-stack",      # right family, wrong core stack/skills
    "seniority-mismatch",  # right work, wrong level
    "too-generic",         # posting too vague to establish fit
    "non-engineering",     # not a software-adjacent role at all
    "other",
)


@dataclass(frozen=True)
class EvalCase:
    id: str
    fixture: str
    profile: str
    relevant: str
    not_relevant: str


@dataclass(frozen=True)
class Verdict:
    job_id: int
    relevant: bool
    category: str  # "" when relevant; one of CATEGORIES (or "judge-omitted") otherwise
    reason: str


def load_cases(path: str | Path) -> list[EvalCase]:
    payload = json.loads(Path(path).read_text())
    return [
        EvalCase(
            id=c["id"], fixture=c["fixture"], profile=c["profile"],
            relevant=c["relevant"], not_relevant=c["not_relevant"],
        )
        for c in payload["cases"]
    ]


# --------------------------------------------------------------------------- #
# The judge (one Claude call per case, all postings batched).
# --------------------------------------------------------------------------- #
def build_judge_prompt(case: EvalCase, jobs: list[Job], *, desc_chars: int = 400) -> str:
    blocks = []
    for job in jobs:
        desc = re.sub(r"<[^>]+>", " ", job.description)
        desc = re.sub(r"\s+", " ", desc).strip()[:desc_chars]
        blocks.append(
            f"### POSTING id={job.id}\nTitle: {job.title}\n"
            f"Company: {job.company}\nDescription: {desc}"
        )
    return (
        "You are an evaluation judge for a job-search agent. For EACH posting "
        "below, decide whether it is RELEVANT for the candidate profile under "
        "the rubric given. Judge strictly against the rubric, not general "
        "plausibility. For every non-relevant posting pick ONE failure "
        f"category from: {', '.join(CATEGORIES)}.\n\n"
        "Respond with ONLY a JSON object, no prose, no markdown fences:\n"
        '{"judgments": [{"id": <posting id>, "relevant": true|false, '
        '"category": "<empty string if relevant>", '
        '"reason": "<one short sentence>"}]}\n\n'
        f"=== CANDIDATE PROFILE ===\n{case.profile}\n\n"
        f"=== RELEVANT means ===\n{case.relevant}\n\n"
        f"=== NOT RELEVANT means ===\n{case.not_relevant}\n\n"
        f"=== POSTINGS ===\n" + "\n\n".join(blocks) + "\n"
    )


def parse_judgments(payload: dict, job_ids: list[int]) -> dict[int, Verdict]:
    """Turn the judge's JSON into verdicts, one per expected job id.

    Postings the judge skipped are counted NOT relevant ("judge-omitted") — an
    unjudged posting must never inflate precision."""
    verdicts: dict[int, Verdict] = {}
    for entry in payload.get("judgments", []):
        try:
            job_id = int(entry["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if job_id not in job_ids:
            continue
        relevant = bool(entry.get("relevant", False))
        category = "" if relevant else str(entry.get("category", "other")).strip()
        if not relevant and category not in CATEGORIES:
            category = "other"
        verdicts[job_id] = Verdict(
            job_id, relevant, category, str(entry.get("reason", "")).strip()
        )
    for job_id in job_ids:
        verdicts.setdefault(
            job_id, Verdict(job_id, False, "judge-omitted", "judge skipped this posting")
        )
    return verdicts


def judge_jobs(
    case: EvalCase,
    jobs: list[Job],
    *,
    claude_path: str | None = None,
    home: str | None = None,
    model: str | None = None,
) -> dict[int, Verdict]:
    """Judge every posting for one case in a single Claude call."""
    if not jobs:
        return {}
    raw = claude_cli.run_claude(
        build_judge_prompt(case, jobs),
        claude_path=claude_path, home=home, model=model, timeout=240,
    )
    return parse_judgments(claude_cli.extract_json(raw), [j.id for j in jobs])


# --------------------------------------------------------------------------- #
# Metrics (pure functions over verdicts).
# --------------------------------------------------------------------------- #
def precision_at_k(top_ids: list[int], verdicts: dict[int, Verdict], k: int = 5) -> float:
    """Judged-relevant fraction of the first k postings (of those that exist)."""
    head = top_ids[:k]
    if not head:
        return 0.0
    hits = sum(1 for job_id in head if verdicts.get(job_id, None) and verdicts[job_id].relevant)
    return hits / len(head)


def task_success(
    top_ids: list[int], verdicts: dict[int, Verdict], *, k: int = 5, need: int = 3
) -> bool:
    """The task succeeds when at least `need` of the top `k` are judged relevant."""
    head = top_ids[:k]
    hits = sum(1 for job_id in head if verdicts.get(job_id) and verdicts[job_id].relevant)
    return hits >= need


def failure_counts(verdicts_by_case: dict[str, dict[int, Verdict]]) -> dict[str, int]:
    """Tally non-relevant categories across all cases (for the error taxonomy)."""
    counts: dict[str, int] = {}
    for verdicts in verdicts_by_case.values():
        for v in verdicts.values():
            if not v.relevant:
                counts[v.category] = counts.get(v.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def summarize(case_rows: list[dict]) -> dict:
    """Aggregate per-case rows (see run_eval.py for the row shape) into the
    headline numbers for one arm (full / round1 / fallback)."""
    n = len(case_rows)
    if n == 0:
        return {}
    successes = sum(1 for r in case_rows if r["success"])
    recovery_pool = [r for r in case_rows if r.get("recovery_opportunity")]
    recovered = sum(1 for r in recovery_pool if r["success"])
    return {
        "n_cases": n,
        "success_rate": successes / n,
        "mean_precision_at_5": sum(r["precision_at_5"] for r in case_rows) / n,
        "mean_rounds": sum(r["rounds_used"] for r in case_rows) / n,
        "early_stop_rate": sum(1 for r in case_rows if r["early_stop"]) / n,
        "recovery_opportunities": len(recovery_pool),
        "recovered": recovered,
        "recovery_rate": (recovered / len(recovery_pool)) if recovery_pool else None,
    }
