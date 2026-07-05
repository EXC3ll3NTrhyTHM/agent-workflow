# Week 4 — Midpoint Check

Name: Blake Simpson  Week: 4 (Midpoint)  Track: Track 3 — Agent

Live-demo notes for the midpoint meeting, organized around the four rubric
criteria.

## 1. Working system

The agent runs end to end on real inputs: résumé in → multi-source job search →
batched Claude scoring → ranked list → email alert for strong matches.

Demo commands:

```bash
# One résumé through the full loop (search → score → refine → alert):
PYTHONPATH=src .venv/bin/python -m job_scout.main tests/fixtures/resume_ml_engineer.md

# All 5 test tasks (writes docs/baseline_outputs.md):
PYTHONPATH=src .venv/bin/python scripts/run_baseline.py
```

## 2. Improvement over baseline

Two meaningful changes since the Week 3 baseline, both with evidence.

### a. Search recall: third source + smarter relevance filter

The Week 3 corpus was RemoteOK (~100 jobs) + Remotive's degraded cached feed
(~32 jobs), filtered by naive substring matching. Two problems measured:

- Thin corpus: the DevOps test task found **0 good matches** in Week 3 — the
  corpus simply contained no real SRE jobs (best score: 6.0 for a
  customer-facing "Field Reliability Engineer").
- Weak filter: substring matching let description-only hits outrank real
  matches ("api" matched "therapist"-style false positives; a generic Product
  Manager posting outranked actual DevOps jobs).

Changes (`src/job_scout/jobicy.py`, `src/job_scout/jobs.py`):

- Added **Jobicy** as a third source (~100 remote, English, tagged jobs).
- Filter now matches at **word starts only** ("ml" matches "MLOps", not
  "html") and ranks by hits in the high-signal fields (title, tags) before
  description hits.

Measured on one fixed representative query per test task (relevant = a core
role term appears in the title/tags of a returned job):

| Test task | Before | After |
|---|---|---|
| python-backend | 2/8 | 3/8 |
| react-frontend | 4/8 | 8/8 |
| ml-engineer | 3/8 | 5/8 |
| devops-sre | **0/5** | 3/8 |
| data-analyst | 5/8 | 6/8 |
| **Total** | **14/37 (38%)** | **25/40 (63%)** |

Corpus size: 131 → 230 postings. The DevOps query now surfaces a Senior DevOps
Engineer, a Site Reliability Engineer, and a Senior Cloud Engineer at the top —
Week 3 returned none of these because they didn't exist in the corpus.

**End-to-end re-run** (full agent loop with live Claude on all 5 test tasks,
2026-07-04; "good" = scored ≥ 7 by Claude; Week 3 run preserved in
`baseline_outputs_week3.md`, new run in `baseline_outputs.md`):

| Test task | Week 3 good / best | Week 4 good / best | Rounds needed |
|---|---|---|---|
| data-analyst | 0 / 4.0 | 2 / **9.0** | 2 → 2 |
| devops-sre | 0 / 6.0 | 3 / **9.0, 9.0** | 2 → **1** |
| ml-engineer | 1 / 9.0 | 3 / 8.0 | 2 → **1** |
| python-backend | 0 / 4.0 | 0 / 6.0 | 2 → 2 |
| react-frontend | 1 / 7.0 | 1 / 7.0 | 2 → 2 |

Two second-order effects worth noting in the demo:

- DevOps and ML now hit their "3 good matches" target in **one round** — the
  self-correction loop stops early, which halves the Claude calls for those
  runs. Better recall made the agent cheaper, not just more accurate.
- python-backend still finds 0 good matches: today's feeds genuinely contain
  no Python-backend-titled roles (the closest is a DevOps posting Claude
  scored 6.0). Claude scoring the mismatches low is correct behavior — this
  is a corpus-coverage gap, not a bug (see Failure 2). Scores also vary with
  the live feed day to day: Week 3's single 9.0 for ML was a posting that has
  since left the feeds.

### b. Email-alert step (Week 4 roadmap item)

`src/job_scout/alerts.py`: one digest email per run over Gmail SMTP (app
password), wired into the CLI. Safeguards:

- **Dedup** via the existing `db.mark_alerted` — a posting is only ever
  alerted on once, so a daily cron run doesn't re-send the same job.
- **Dry-run mode** when credentials are absent: prints the composed email
  instead of sending, and does *not* mark postings as alerted. Verified: a
  simulated second run correctly excluded the already-alerted posting.

## 3. Failure analysis

### Failure 1 — Remotive serves a stale cache that ignores the search query (root-caused Week 3, still present)

Re-verified 2026-07-04: two different search queries return byte-identical job
IDs; the response carries `age: 64380` (~18 h) and `cache: HIT`. Root cause:
Remotive's CDN caches one response and serves it regardless of query string —
server-side search is effectively down for the public API. **Fix adopted:**
treat every source as an untrusted feed — pull full feeds, merge, and search
client-side. Remotive stays in the mix (its ~30 postings are still real jobs)
but nothing depends on its search working. Lesson: verify a data source
returns *relevant* results, not just an HTTP 200.

### Failure 2 — Corpus gaps, not scoring, caused bad Week 3 results

The Week 3 DevOps and data-analyst runs looked like scoring failures (top
score 6.0 and 4.0). Root cause was upstream: the corpus contained no matching
jobs, and Claude correctly scored the mismatches low. The scoring layer was
fine; recall was the bottleneck. This reframed Week 4 priorities — fixing
search recall (above) mattered more than tuning the scorer.

### Failure 3 — Score drift near the alert threshold (measured this week)

New tool: `scripts/score_stability.py` scores the same 8 postings against the
same résumé 3 times with live Claude and measures the spread. Results
(ML-engineer fixture, 2026-07-04):

- Mean drift 0.50 points, max drift 1.0 — scores are quite stable overall.
- **0/8** postings flipped across the "good" bar (7.0).
- **1/8** flipped across the **alert** bar (9.0): "Senior ML Engineer (Token
  Factory)" scored 8, 8, 9 across runs — it would email-alert on some days
  and not others.

Confirmed on my real résumé (2026-07-05): across repeat runs the top match
(Senior AI Engineer Architect @ Lemon.io) wobbles between 8 and 9, and the
runner-up did the same — but the *ranking order held steady* in every run.

Root cause is two effects stacking:

1. **LLM sampling is nondeterministic** — each scoring call is a fresh
   generation, and the `claude` CLI exposes no temperature control, so an
   "excellent fit" can legitimately come back as an 8 one run and a 9 the
   next.
2. **The integer 0–10 scale amplifies it** — the smallest possible
   disagreement is a full point, so a "true 8.5" job has nowhere to land
   except 8 or 9, and it alternates.

The key distinction: **rank stability is what the ranked list needs, and rank
order is stable; absolute-score stability only matters at the alert
threshold** — and the hard 9.0 bar sat exactly on the drift boundary.
Mitigation chosen: **lower the alert threshold to 8**. Because alerts are
deduped, the cost of a slightly looser bar is one extra email ever per
borderline job, whereas the cost of the hard 9.0 bar is strong matches
alerting only on lucky days (or a borderline job's single alert arriving a
day late).

If drift itself ever needs shrinking, the options in increasing cost are:
anchored score-band definitions in the prompt ("9–10 = meets all core skills
and seniority"), a finer 0–100 scale, sub-criteria scores (skills /
seniority / domain) averaged into a fractional score, or scoring each batch
2–3 times and averaging. All stay on the shelf unless bad alert behavior
shows up at threshold 8.

## 4. Revised scope statement

**Original scope (Week 1):** an agent that reads a résumé, searches job
boards, scores matches with an LLM, and emails alerts for strong matches, run
on a schedule.

**Assessment: achievable — core scope is now built.** Search, scoring, the
agent loop, persistence, and email alerts all exist and run. Adjustments:

- **Kept:** résumé → search → score → alert pipeline; SQLite memory; nightly
  scheduled run (cron wiring is trivial now that the CLI is idempotent
  thanks to alert dedup).
- **Adjusted:** "search job boards" now means *aggregate multiple full feeds
  and search client-side* rather than relying on any board's search API —
  forced by the Remotive failure, and strictly more robust.
- **At risk / cut if needed:** the LangGraph port of the loop is a
  nice-to-have, not scope — the plain-Python loop already exhibits the
  agentic behaviors (memory, self-correction, early stopping). The Week 6
  eval harness (20 tasks + rubric) stays in scope.

## Next steps (Week 5)

- Wire real Gmail credentials and a nightly cron/launchd run.
- Grow the corpus further (candidate: Arbeitnow — probed, but only ~13% of
  its feed is remote and it skews German-market, so it needs pagination and
  filtering to be worth it).
- Act on the score-stability findings (below) for the alert threshold.
