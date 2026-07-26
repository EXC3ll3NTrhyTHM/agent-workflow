"""Week 6 evaluation harness: run the agent on every test case and grade it.

Three arms per case, compared in the writeup:
- full     — the real agent (Claude scorer + up to 3 refinement rounds).
- round1   — no-refinement ablation: the full run truncated to its first round
             (reconstructed from RoundLog.job_ids, so it costs nothing extra).
- fallback — the keyword-overlap baseline: the agent run with Claude disabled
             (claude_path pointed at a nonexistent binary), so query derivation
             and scoring both take their deterministic fallback paths.

Every posting any arm surfaced is judged ONCE per case (single batched Claude
call) against the case's rubric in tests/eval_cases.json; all arms are then
graded from the same verdict set. Results land in docs/eval/results.json plus
a markdown summary table in docs/eval/results.md.

Usage:
    PYTHONPATH=src python scripts/run_eval.py [--cases id1,id2] [--out docs/eval]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from job_scout import evaluation, jobs as jobs_mod
from job_scout.agent import run_agent
from job_scout.config import Config

FIXTURES = ROOT / "tests" / "fixtures"
CASES_PATH = ROOT / "tests" / "eval_cases.json"
TOP_K, NEED = 5, 3
TARGET_GOOD = 3  # mirrors run_agent's default; round-1 n_good below this is a
                 # recovery opportunity for the refinement loop

# A path that never exists: forces every Claude tool call down its fallback.
DISABLED_CLAUDE = "/nonexistent/claude-disabled-for-eval"


def arm_row(arm: str, top_ids: list[int], verdicts, *, rounds_used: int,
            early_stop: bool, recovery_opportunity: bool, wall_s: float) -> dict:
    return {
        "arm": arm,
        "top_ids": top_ids[:TOP_K],
        "precision_at_5": evaluation.precision_at_k(top_ids, verdicts, TOP_K),
        "success": evaluation.task_success(top_ids, verdicts, k=TOP_K, need=NEED),
        "rounds_used": rounds_used,
        "early_stop": early_stop,
        "recovery_opportunity": recovery_opportunity,
        "wall_seconds": round(wall_s, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", help="comma-separated case ids (default: all)")
    parser.add_argument("--out", default=str(ROOT / "docs" / "eval"))
    args = parser.parse_args()

    cfg = Config.from_env()
    cases = evaluation.load_cases(CASES_PATH)
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c.id in wanted]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"evaluating {len(cases)} case(s); corpus warming up...", flush=True)
    corpus = jobs_mod.load_corpus()
    print(f"corpus: {len(corpus)} unique postings\n", flush=True)

    results: dict = {"cases": {}, "corpus_size": len(corpus)}
    for i, case in enumerate(cases, 1):
        resume_text = (FIXTURES / case.fixture).read_text()
        print(f"[{i}/{len(cases)}] {case.id}: full agent run...", flush=True)

        t0 = time.monotonic()
        full = run_agent(
            resume_text, resume_label=case.id,
            claude_path=cfg.claude_path, home=cfg.claude_home, model=cfg.model,
            verbose=True,
        )
        full_wall = time.monotonic() - t0
        # "none" rounds (nothing new to score) are fine; "fallback" means the
        # Claude call failed and the numbers measure the wrong thing.
        scorers = {r.scorer for r in full.rounds}
        if "fallback" in scorers:
            print(f"  WARNING: fallback scorer in full arm ({scorers}) — "
                  "this case's full-arm numbers measure the fallback, not the agent.",
                  flush=True)

        print(f"  fallback baseline run...", flush=True)
        t0 = time.monotonic()
        fallback = run_agent(
            resume_text, resume_label=f"{case.id}-fallback",
            claude_path=DISABLED_CLAUDE, verbose=False,
        )
        fb_wall = time.monotonic() - t0

        # Judge every posting either arm surfaced, in one call.
        by_id = {s.job.id: s.job for s in full.scored}
        by_id.update({s.job.id: s.job for s in fallback.scored})
        all_jobs = list(by_id.values())
        print(f"  judging {len(all_jobs)} unique postings...", flush=True)
        verdicts = evaluation.judge_jobs(
            case, all_jobs,
            claude_path=cfg.claude_path, home=cfg.claude_home, model=cfg.model,
        )

        full_top = [s.job.id for s in full.scored]
        # Round-1 ablation: only postings the first round surfaced, in final-
        # score order. (Scores are per-posting bests; for round-1 postings that
        # reappeared later this can be slightly generous to the ablation.)
        r1_ids = set(full.rounds[0].job_ids) if full.rounds else set()
        r1_top = [job_id for job_id in full_top if job_id in r1_ids]
        fb_top = [s.job.id for s in fallback.scored]

        opportunity = bool(full.rounds) and full.rounds[0].n_good < TARGET_GOOD
        rows = {
            "full": arm_row(
                "full", full_top, verdicts,
                rounds_used=len(full.rounds),
                early_stop=len(full.rounds) < 3,
                recovery_opportunity=opportunity, wall_s=full_wall,
            ),
            "round1": arm_row(
                "round1", r1_top, verdicts,
                rounds_used=1, early_stop=False,
                recovery_opportunity=opportunity, wall_s=0.0,
            ),
            "fallback": arm_row(
                "fallback", fb_top, verdicts,
                rounds_used=len(fallback.rounds),
                early_stop=len(fallback.rounds) < 3,
                recovery_opportunity=False, wall_s=fb_wall,
            ),
        }
        results["cases"][case.id] = {
            "profile": case.profile,
            "arms": rows,
            "full_queries": full.tried_queries,
            "full_rounds": [
                {"query": r.query, "n_jobs": r.n_jobs, "n_good": r.n_good,
                 "scorer": r.scorer}
                for r in full.rounds
            ],
            "fallback_queries": fallback.tried_queries,
            "judgments": {
                str(v.job_id): {
                    "relevant": v.relevant, "category": v.category,
                    "reason": v.reason,
                    "title": by_id[v.job_id].title,
                    "company": by_id[v.job_id].company,
                }
                for v in verdicts.values()
            },
        }
        f, r1, fb = (rows[a] for a in ("full", "round1", "fallback"))
        print(f"  p@5 full={f['precision_at_5']:.2f} round1={r1['precision_at_5']:.2f} "
              f"fallback={fb['precision_at_5']:.2f}  "
              f"success full={f['success']} round1={r1['success']} fallback={fb['success']}\n",
              flush=True)

    # Aggregate each arm across cases.
    summary = {
        arm: evaluation.summarize(
            [results["cases"][c]["arms"][arm] for c in results["cases"]]
        )
        for arm in ("full", "round1", "fallback")
    }
    verdicts_by_case = {
        cid: {
            int(job_id): evaluation.Verdict(
                int(job_id), j["relevant"], j["category"], j["reason"]
            )
            for job_id, j in results["cases"][cid]["judgments"].items()
        }
        for cid in results["cases"]
    }
    results["summary"] = summary
    results["failure_categories"] = evaluation.failure_counts(verdicts_by_case)

    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    (out_dir / "results.md").write_text(render_markdown(results))
    print(f"wrote {out_dir / 'results.json'} and results.md")
    for arm, s in summary.items():
        print(f"{arm:>9}: success {s['success_rate']:.0%}  "
              f"p@5 {s['mean_precision_at_5']:.2f}  "
              f"rounds {s['mean_rounds']:.1f}")
    return 0


def render_markdown(results: dict) -> str:
    lines = [
        "# Evaluation Results",
        "",
        f"Corpus size at run time: {results['corpus_size']} unique postings.",
        "",
        "## Per-case results",
        "",
        "| Case | Arm | Success | P@5 | Rounds | Wall (s) |",
        "|---|---|---|---|---|---|",
    ]
    for cid, case in results["cases"].items():
        for arm, row in case["arms"].items():
            lines.append(
                f"| {cid} | {arm} | {'PASS' if row['success'] else 'fail'} "
                f"| {row['precision_at_5']:.2f} | {row['rounds_used']} "
                f"| {row['wall_seconds']} |"
            )
    lines += ["", "## Summary", "",
              "| Arm | Success rate | Mean P@5 | Mean rounds | Early-stop | Recovery |",
              "|---|---|---|---|---|---|"]
    for arm, s in results["summary"].items():
        rec = (f"{s['recovered']}/{s['recovery_opportunities']}"
               if s["recovery_opportunities"] else "n/a")
        lines.append(
            f"| {arm} | {s['success_rate']:.0%} | {s['mean_precision_at_5']:.2f} "
            f"| {s['mean_rounds']:.1f} | {s['early_stop_rate']:.0%} | {rec} |"
        )
    lines += ["", "## Failure categories (judged non-relevant postings)", ""]
    for cat, n in results["failure_categories"].items():
        lines.append(f"- {cat}: {n}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
