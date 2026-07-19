"""Offline tests for the Week 6 evaluation module — no network, no Claude.

Run with: .venv/bin/python -m pytest tests/
"""

from __future__ import annotations

from pathlib import Path

import pytest

from job_scout import evaluation
from job_scout.evaluation import Verdict
from job_scout.remotive import Job

ROOT = Path(__file__).resolve().parents[1]


def make_job(job_id: int, title: str = "Backend Engineer") -> Job:
    return Job(
        id=job_id, title=title, company=f"Co{job_id}", category="software-dev",
        url=f"https://example.com/{job_id}", location="Remote",
        description="<p>Python, APIs, SQL.</p>",
    )


def make_case() -> evaluation.EvalCase:
    return evaluation.EvalCase(
        id="test", fixture="resume_python_backend.md", profile="Backend dev",
        relevant="Backend roles.", not_relevant="Frontend roles.",
    )


# --------------------------------------------------------------------------- #
# Test-set integrity
# --------------------------------------------------------------------------- #
def test_eval_cases_load_and_fixtures_exist():
    cases = evaluation.load_cases(ROOT / "tests" / "eval_cases.json")
    assert len(cases) >= 10  # assignment floor
    assert len({c.id for c in cases}) == len(cases)
    for case in cases:
        assert (ROOT / "tests" / "fixtures" / case.fixture).is_file()
        assert case.relevant and case.not_relevant


# --------------------------------------------------------------------------- #
# Judge prompt + parsing
# --------------------------------------------------------------------------- #
def test_build_judge_prompt_contains_rubric_and_strips_html():
    prompt = evaluation.build_judge_prompt(make_case(), [make_job(7)])
    assert "Backend roles." in prompt
    assert "id=7" in prompt
    assert "<p>" not in prompt


def test_parse_judgments_normalizes_and_covers_all_ids():
    payload = {"judgments": [
        {"id": 1, "relevant": True, "category": "ignored", "reason": "fits"},
        {"id": "2", "relevant": False, "category": "adjacent-stack", "reason": "Java"},
        {"id": 3, "relevant": False, "category": "not-a-real-category", "reason": "?"},
        {"id": 99, "relevant": True},  # not an expected id — dropped
    ]}
    verdicts = evaluation.parse_judgments(payload, [1, 2, 3, 4])
    assert verdicts[1].relevant and verdicts[1].category == ""
    assert not verdicts[2].relevant and verdicts[2].category == "adjacent-stack"
    assert verdicts[3].category == "other"  # unknown category normalized
    assert verdicts[4].category == "judge-omitted"  # skipped => counted not relevant
    assert not verdicts[4].relevant
    assert 99 not in verdicts


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _verdicts(flags: dict[int, bool]) -> dict[int, Verdict]:
    return {
        job_id: Verdict(job_id, ok, "" if ok else "other", "r")
        for job_id, ok in flags.items()
    }


def test_precision_at_k():
    v = _verdicts({1: True, 2: False, 3: True, 4: True, 5: False, 6: True})
    assert evaluation.precision_at_k([1, 2, 3, 4, 5, 6], v, 5) == 3 / 5
    # Shorter list than k: precision over what exists, not padded with misses.
    assert evaluation.precision_at_k([1, 2], v, 5) == 1 / 2
    assert evaluation.precision_at_k([], v, 5) == 0.0


def test_task_success_needs_three_of_top_five():
    v = _verdicts({1: True, 2: True, 3: False, 4: False, 5: False, 6: True})
    assert evaluation.task_success([1, 2, 3, 4, 6], v)       # 3 relevant in top 5
    assert not evaluation.task_success([1, 3, 4, 5, 2], v)   # only 2 relevant
    # A relevant posting at rank 6 must not help a top-5 metric.
    assert not evaluation.task_success([1, 2, 3, 4, 5, 6], v)


def test_failure_counts_tallies_across_cases():
    by_case = {
        "a": _verdicts({1: False, 2: True}),
        "b": {3: Verdict(3, False, "adjacent-stack", "r"),
              4: Verdict(4, False, "adjacent-stack", "r")},
    }
    assert evaluation.failure_counts(by_case) == {"adjacent-stack": 2, "other": 1}


def test_summarize_aggregates_and_computes_recovery():
    rows = [
        {"success": True, "precision_at_5": 0.8, "rounds_used": 1,
         "early_stop": True, "recovery_opportunity": False},
        {"success": True, "precision_at_5": 0.6, "rounds_used": 3,
         "early_stop": False, "recovery_opportunity": True},   # rescued by refinement
        {"success": False, "precision_at_5": 0.2, "rounds_used": 3,
         "early_stop": False, "recovery_opportunity": True},   # not rescued
        {"success": True, "precision_at_5": 1.0, "rounds_used": 2,
         "early_stop": True, "recovery_opportunity": False},
    ]
    s = evaluation.summarize(rows)
    assert s["n_cases"] == 4
    assert s["success_rate"] == 3 / 4
    assert s["mean_precision_at_5"] == pytest.approx(0.65)
    assert s["recovery_opportunities"] == 2
    assert s["recovered"] == 1
    assert s["recovery_rate"] == 1 / 2
    assert s["early_stop_rate"] == 1 / 2


def test_summarize_empty_and_no_opportunities():
    assert evaluation.summarize([]) == {}
    rows = [{"success": True, "precision_at_5": 1.0, "rounds_used": 1,
             "early_stop": True, "recovery_opportunity": False}]
    assert evaluation.summarize(rows)["recovery_rate"] is None
