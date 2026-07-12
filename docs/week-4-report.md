# Week 4 Progress Report

Name: Blake Simpson  Week: 4 (Midpoint) Track: Track 3 — Agent

## What I did this week

- Added 3rd job source(Jobicy, ~100 remote jobs) as there still werent enough jobs being returned from the queries. 
- Rewrote the ranking to match on title/tag instead of description which increased recall on the test queries from 38% to 63%. 
- Built out email alerts, has existing jobs marked so that duplicate emails arent sent.
- Use score stability script to measure how much Claude's scores drift between identical runs; used this to lower the alert threshold to 8 from 9.
- Verfied end to end flow with my real resume and I get email alerts when this runs

## What worked

- The full pipeline worked on real input on the first try: my PDF résumé extracted cleanly, the agent derived sensible queries from it, and the SMTP send worked immediately (including the alert dedup correctly staying silent on the second run).

## What Failed or Surprised me

- Remotive's API is still broken two weeks later, re-verified that different search queries return byte-identical results from an ~18-hour-old CDN cache. The multi-source design absorbed this, but I've stopped expecting it to recover.
- The python-backend job test still finds 0 good matches even with the bigger corpus. It looked like a scoring failure but it's a coverage gap: today's feeds genuinely contain no Python-backend roles, and Claude scoring the mismatches low is correct behavior.
- Score drift is real but not very impactful. The rankings are stable (the best job stays on top) but absolute scores wobble ~1 point. The top match scored 8 one run and 9 the next. With a hard threshold of 9 it would have alerted only on lucky days, which is why the threshold is now 8.

## What I learned

- Rank stability and score stability are different properties. The ranked list needs the first, and only the alert threshold needs the second, so instead of an expensive fix (multi-pass scoring, finer scales), moving the threshold off the drift boundary was enough, and the alert dedup makes the looser bar nearly free.
- When an agent produces bad output, check the data layer before blaming the model. Both "failures" this week (DevOps in Week 3, python-backend now) were corpus gaps that Claude was scoring correctly.

## Evidence of Progress

- Midpoint doc with before/after tables and failure analysis: `docs/week-4-midpoint.md`
- Week 3 vs Week 4 baseline outputs, same 5 test tasks: `docs/baseline_outputs_week3.md` vs `docs/baseline_outputs.md`
- New code: `src/job_scout/jobicy.py`, `src/job_scout/alerts.py`, `scripts/score_stability.py`
- Commit: https://github.com/EXC3ll3NTrhyTHM/agent-workflow/commit/1d92d15
- Sample (my real résumé, live run — the agent self-corrected after round 1 and the dedup suppressed a repeat alert):

```
round 1/3: searching the job corpus for 'AI engineer Java'...
  scored [claude]: 2 good match(es) >= 7.0 so far (best 9.0)
  not enough good matches — deriving a fresh query (Claude, ~10-30s)...
round 2/3: searching the job corpus for 'llm engineer python'...
  scored [claude]: 3 good match(es) >= 7.0 so far (best 9.0)
  target of 3 good matches reached — stopping early
...
1 alert-worthy (>= 8.5):
   9.0  Senior AI Engineer Architect  @ Lemon.io
All alert-worthy postings were already alerted on — no email.
```

## Plan for Next week

- Schedule the daily cron job
- Start building the Week 6 eval harness: 20 test tasks (résumé profiles + expected relevance criteria) and a scoring rubric.
- Watch alert quality at threshold 8; if weak matches start emailing, try anchored score-band definitions in the scoring prompt before anything heavier.

## Blockers

- None
