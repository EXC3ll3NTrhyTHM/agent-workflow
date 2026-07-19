# Week 6 Progress Report

Name: Blake Simpson  Week: 6 (Evaluation) Track: Track 3 — Agent

## What I did this week

- Built the evalutionation stuff. There are 12 test cases. 10 realistic resume profiles, 1 test cases that tests how well the jobs cover different fields, and one edge case that's a career-changer to test a resume with low qualifying attributes.
- The tests are in 3 parts: the full agent, a no-refinement result, and a keywork-fallback baseline with Claude disabled.
- It tracks task success rate, precision, step efficientcy, and error recovery rate.
- Full writeup in `docs/evaluation.md`; raw results in `docs/eval/`.

## What worked

- All of it works pretty much the way it was expected with the expection of one bit.

## What Failed or Surprised me

- The 17% success rate intitially concerned me but after further investigation it was determined this is again an issue with the corpus being used to feed this system. There were only 241 postings to choose from and 10 out of 12 tests returned fewer than 3 relevant postings. The 2 cases that that matched up with the real postings the agent was successful in ranking and judged them correctly. So again the problem I am running into is job supply not agent judgement


## What I learned

- The success metric needs to be adjusted according to the task fesasibility. More job sources need to be added to have a higher success metric.

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
