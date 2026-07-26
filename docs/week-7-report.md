# Week 7 Progress Report

Name: Blake Simpson  Week: 7 (Polish + final report draft) Track: Track 3 — Agent

## What I did this week

- Fixed the top 3 issues from the Week 6 eval:
  1. **More jobs**: added two sources (We Work Remotely, Working Nomads):
     241 -> ~710 postings.
  2. **No padding**: search returns nothing instead of filler, wrong-role
     jobs cap at a score of 3, and the CLI admits "nothing scored 7+ today."
  3. **Smarter stopping**: the agent quits hopeless searches instead of
     burning all 3 rounds.
- Re-ran the 12 eval cases: success 2/12 -> 8/12, precision@5 0.32 -> 0.65
  (full tables in `docs/eval/results.md`).
- Cleanup: removed unused dependencies, fixed a job-id bug that could re-send
  alerts, rewrote the README, verified a fresh clone runs (25 tests pass).
- Drafted the final report (`docs/final-report.md`) and the Week 8 slide deck
  (`docs/week-8-deck.md`).

## What worked

- Reusing the same 12 test cases made the before/after numbers directly
  comparable.
- The supply fix worked as predicted: winnable cases went from 2 to 8 and the
  agent passed all 8. The remaining fails just had too few relevant postings
  to pass — and the agent found every one that existed.
- The new stop rule fired exactly where intended: two hopeless cases stopped
  at round 2 instead of wasting a third.

## What failed or surprised me

- My first stop rule (quit when two queries find nothing new) almost never
  fires on the bigger corpus — hopeless queries now find new-but-irrelevant
  jobs instead of nothing. The eval data pointed to a better rule (zero good
  matches after two rounds -> stop) and killed a stricter one that would have
  cost python_backend a win.
- The no-Claude baseline also jumped (1/12 -> 7/12) just from the corpus fix —
  most of this week's gain was supply, as Week 6 predicted.

## What I learned

- Fixing supply (adding RSS feeds) moved the numbers more than any agent-logic
  change all project - confirmation that evaluating before optimizing was the
  right call.

## Evidence of progress

- New code: `src/job_scout/weworkremotely.py`, `src/job_scout/workingnomads.py`,
  `src/job_scout/ids.py`, `tests/test_week7_fixes.py` (25 tests total, passing)
- Changed: `jobs.py` (no padding), `agent.py` (exhaustion stop, score-only-new,
  stop_reason), `tools.py` (calibrated scoring prompt), `main.py` (honest output)
- Results: `docs/eval/results.md` / `results.json` (Week 7 re-run),
  `docs/evaluation.md` 9 (before/after)
- Report + deck: `docs/final-report.md`, `docs/week-8-deck.md`

## Plan for next week

- Demo the final prototype

## Blockers

- None
