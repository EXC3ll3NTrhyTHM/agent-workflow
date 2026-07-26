"""Offline tests for the Week 7 fixes driven by the Week 6 evaluation:

1. Honest search — ``jobs.search`` returns an empty list when nothing matches
   instead of padding with the head of the corpus.
2. Hopelessness stop — the agent stops after two consecutive rounds that
   surface nothing new, instead of burning every round's Claude calls.
3. Scoring efficiency — postings already scored in an earlier round are not
   sent back to the scorer.
4. Stable ids — digest-based ids are identical across processes (alert dedup
   in SQLite depends on this).

No network, no Claude — sources and tools are monkeypatched.
"""

from __future__ import annotations

import pytest

from job_scout import agent, jobs, tools
from job_scout.ids import stable_id
from job_scout.remotive import Job


def make_job(job_id: int, title: str, category: str = "") -> Job:
    return Job(
        id=job_id, title=title, company=f"Co{job_id}", category=category,
        url=f"https://example.com/{job_id}", location="Remote",
        description=f"{title} role.",
    )


@pytest.fixture
def corpus(monkeypatch):
    postings = [
        make_job(1, "Senior Python Backend Engineer", "python, api"),
        make_job(2, "React Frontend Developer", "javascript, react"),
        make_job(3, "Head of Sales"),
    ]
    monkeypatch.setattr(jobs, "_corpus", postings)
    return postings


# --------------------------------------------------------------------------- #
# 1. Honest search: no padding when nothing matches
# --------------------------------------------------------------------------- #
def test_search_returns_empty_when_nothing_matches(corpus):
    assert jobs.search("underwater basket weaving") == []


def test_search_returns_empty_for_stopword_only_query(corpus):
    assert jobs.search("remote senior engineer") == []


def test_search_still_finds_real_matches(corpus):
    hits = jobs.search("python backend")
    assert [j.id for j in hits] == [1]


# --------------------------------------------------------------------------- #
# 2 + 3. Agent loop: hopelessness stop and score-only-new
# --------------------------------------------------------------------------- #
def run_stub_agent(monkeypatch, search_results, scores):
    """Run the agent with canned search results and scores; return
    (result, scored_batches) where scored_batches records what reached the
    scorer each round."""
    queries = iter([f"query {n}" for n in range(1, 10)])
    scored_batches: list[list[int]] = []

    monkeypatch.setattr(tools, "derive_query", lambda *a, **k: next(queries))
    monkeypatch.setattr(
        tools, "search_jobs",
        lambda q, limit=8: search_results[min(len(scored_batches),
                                              len(search_results) - 1)],
    )

    def fake_score(resume_text, batch, **kwargs):
        scored_batches.append([j.id for j in batch])
        return [tools.ScoredJob(j, scores.get(j.id, 5.0), "stub", "claude")
                for j in batch]

    monkeypatch.setattr(tools, "score_jobs", fake_score)
    result = agent.run_agent("a résumé")
    return result, scored_batches


def test_agent_stops_after_two_dead_rounds(monkeypatch):
    # Every query finds nothing: round 1 and 2 are dead, round 3 never runs.
    result, batches = run_stub_agent(monkeypatch, [[]], scores={})
    assert result.stop_reason == "exhausted"
    assert len(result.rounds) == 2
    assert batches == []  # nothing ever reached the (expensive) scorer
    assert result.scored == []


def test_agent_does_not_rescore_seen_postings(monkeypatch):
    # Both rounds surface the same two mediocre postings: round 1 scores them,
    # round 2 has nothing new — and with zero good matches after two full
    # rounds the agent stops as exhausted rather than trying a third query.
    postings = [make_job(1, "A"), make_job(2, "B")]
    result, batches = run_stub_agent(
        monkeypatch, [postings], scores={1: 6.0, 2: 5.0}
    )
    assert batches == [[1, 2]]  # scored exactly once
    assert result.stop_reason == "exhausted"
    assert len(result.rounds) == 2  # dead round still logged
    assert result.rounds[1].scorer == "none"


def test_agent_stops_when_two_rounds_find_no_good_match(monkeypatch):
    # Fresh (never-seen) postings every round, but none score >= 7: the agent
    # gives up after round 2 instead of burning a third round's Claude calls.
    batches_by_round = [
        [make_job(1, "A"), make_job(2, "B")],
        [make_job(3, "C"), make_job(4, "D")],
        [make_job(5, "E"), make_job(6, "F")],
    ]
    result, batches = run_stub_agent(
        monkeypatch, batches_by_round, scores={i: 4.0 for i in range(1, 7)}
    )
    assert result.stop_reason == "exhausted"
    assert len(result.rounds) == 2
    assert batches == [[1, 2], [3, 4]]  # round 3 never scored


def test_agent_stops_when_target_met(monkeypatch):
    postings = [make_job(i, f"Job {i}") for i in (1, 2, 3)]
    result, _ = run_stub_agent(
        monkeypatch, [postings], scores={1: 9.0, 2: 8.0, 3: 7.5}
    )
    assert result.stop_reason == "target_met"
    assert len(result.rounds) == 1
    assert [s.job.id for s in result.alerts] == [1, 2]


# --------------------------------------------------------------------------- #
# 4. Stable ids
# --------------------------------------------------------------------------- #
def test_stable_id_is_deterministic_and_positive():
    a = stable_id("https://weworkremotely.com/remote-jobs/some-posting")
    assert a == stable_id("https://weworkremotely.com/remote-jobs/some-posting")
    assert a > 0
    assert a != stable_id("https://weworkremotely.com/remote-jobs/other")
