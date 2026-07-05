"""Score-stability check: how much does a posting's Claude score drift?

Scores the SAME job set against the SAME résumé N times and measures the
per-posting spread (max − min across runs). Flagged in Week 2: if scores drift
near the hard alert threshold (9/10), the same job could alert one day and not
the next. This measures whether that risk is real before deciding if the
threshold needs a multi-criteria rubric.

Usage:
    PYTHONPATH=src python scripts/score_stability.py [resume.md] [n_runs]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_scout import tools
from job_scout.config import Config

DEFAULT_RESUME = Path(__file__).resolve().parents[1] / "tests/fixtures/resume_ml_engineer.md"
QUERY = "machine learning engineer llm"
GOOD, ALERT = 7.0, 9.0


def main() -> int:
    resume_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESUME
    n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    resume_text = resume_path.read_text()
    cfg = Config.from_env()

    jobs = tools.search_jobs(QUERY, limit=8)
    print(f"résumé: {resume_path.name}   query: {QUERY!r}   jobs: {len(jobs)}   runs: {n_runs}\n")

    runs: list[dict[int, float]] = []
    for i in range(n_runs):
        scored = tools.score_jobs(
            resume_text, jobs,
            claude_path=cfg.claude_path, home=cfg.claude_home, model=cfg.model,
        )
        sources = {s.source for s in scored}
        if sources != {"claude"}:
            print(f"run {i + 1}: ABORT — non-claude source(s) {sources}; "
                  "stability of the fallback is trivially perfect and not the question.")
            return 1
        runs.append({s.job.id: s.score for s in scored})
        print(f"run {i + 1}: " + " ".join(f"{s.score:4.1f}" for s in scored))

    print(f"\n{'drift':>5}  {'scores':<{6 * n_runs}}  title")
    drifts = []
    flips_good, flips_alert = 0, 0
    for job in jobs:
        scores = [run[job.id] for run in runs]
        drift = max(scores) - min(scores)
        drifts.append(drift)
        flips_good += min(scores) < GOOD <= max(scores)
        flips_alert += min(scores) < ALERT <= max(scores)
        row = " ".join(f"{s:5.1f}" for s in scores)
        print(f"{drift:5.1f}  {row:<{6 * n_runs}}  {job.title[:55]}")

    print(f"\nmean drift: {sum(drifts) / len(drifts):.2f}   max drift: {max(drifts):.1f}")
    print(f"postings flipping across the good bar ({GOOD}): {flips_good}/{len(jobs)}")
    print(f"postings flipping across the alert bar ({ALERT}): {flips_alert}/{len(jobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
