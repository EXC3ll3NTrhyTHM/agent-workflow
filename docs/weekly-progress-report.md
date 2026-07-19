# Week 6 Progress Report

Name: Blake Simpson  Week: 6 (Evaluation) Track: Track 3 — Agent

## What I did this week

Built the evaluation harness and ran it end to end. The test set is 12 cases
(assignment floor is 10): 10 realistic résumé profiles, one corpus-coverage
probe (technical writer), and one deliberate edge case (career-changer with
thin signal), each paired with a hand-written relevance rubric in
`tests/eval_cases.json`. The harness (`scripts/run_eval.py` +
`src/job_scout/evaluation.py`) runs three arms per case — the full agent, a
no-refinement ablation (round 1 only), and the keyword-fallback baseline with
Claude disabled — then grades every surfaced posting once with an LLM judge
applying the case's rubric. Metrics follow the Track 3 guidance: task success
rate, precision@5, step efficiency (rounds used / early stops), and error
recovery rate. Full writeup in `docs/evaluation.md`; raw results in
`docs/eval/`.

## What worked

<<<<<<< Updated upstream
- The digest's very first dry-run against my real database was immediately useful: it surfaced three 7.0 jobs (Nebius, A.Team, Mitre Media) that I had never been alerted about because they sat below the instant threshold. The two-tier design earned its keep before it even shipped.
- The pitch prompt ("use ONLY facts present in the résumé") produced surprisingly specific output on the first try — it cited my on-prem LLM deployment, the genetic prompt-optimization work, and H100 orchestration for the NTT DATA GenAI role, with nothing invented.
- The live SQLite database migrated in place (new `meta` table + `pitch` column) with zero manual steps — the additive-migration approach meant Week 4's data just kept working.
=======
- The three-arm design answered the question I actually cared about at almost
  no extra cost: the round-1 ablation is reconstructed from the full run's
  logs, and the fallback arm needs no Claude calls at all.
- The judge held up under a 30-judgment spot-check (28/30 agreement, and both
  disputes were the judge being *stricter* than me, so the numbers err
  conservative).
- Numbers: full agent 2/12 task success (17%), mean P@5 0.32 vs 0.27 for the
  no-refinement ablation and 0.20 for the keyword baseline.
>>>>>>> Stashed changes

## What Failed or Surprised me

- The headline 17% success rate initially read as "the agent is bad" — but the
  feasibility analysis flipped the story. In 10 of 12 cases the 241-posting
  corpus contained fewer than 3 relevant postings, so success was impossible
  for *any* system. On the 2 feasible cases the agent went 2/2. The bottleneck
  is job supply, not agent judgment — which indicts my Week 3 corpus workaround
  more than the agent built on top of it.
- The keyword fallback *beat* the full agent on the easiest case (devops_sre,
  P@5 0.80 vs 0.60): Claude ranked a generic "Senior Software Engineer" above
  a fourth genuine DevOps role. LLM scoring wins the hard discriminations and
  occasionally overthinks the easy ones.
- Instrumenting step efficiency exposed a real bug: the agent derived a
  next-round query even on its final round — one Claude call per full-length
  run, result discarded. Fixed (`agent.py`).

## What I learned

- Condition your metrics on feasibility or they lie to you. "Task success"
  without "was the task possible" would have sent me off rewriting prompts
  when the actual fix is more job sources.
- The agent's worst behavior is never returning empty-handed: search falls
  back to the head of the corpus and the scorer grades adjacent roles on a
  curve, so infeasible cases produce a confident-looking top-5 of
  wrong-role-family postings (18 of 41 top-5 misses). An honest "1 real match
  today" beats a padded five.

## Evidence of Progress

- New code: `scripts/run_eval.py`, `src/job_scout/evaluation.py`,
  `tests/eval_cases.json`, 7 new résumé fixtures, `tests/test_evaluation.py`
  (17 tests total, all passing)
- Results: `docs/eval/results.md` (summary tables), `docs/eval/results.json`
  (per-posting judgments), `docs/evaluation.md` (full writeup — this becomes
  the final report's evaluation section)

## Plan for Next week

- Act on the eval's #1 finding: expand corpus supply (more feeds / bigger
  pulls), then re-run the same 12 cases to measure the delta — the harness is
  now a regression suite.
- Add an infeasibility-aware stop rule and stop padding the top-5; re-measure
  step efficiency.

## Blockers

- None
