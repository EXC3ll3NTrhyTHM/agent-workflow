# Job Scout Agent — Final Report (Draft)

Name: Blake Simpson · Track: Track 3 — Agent · Repo: https://github.com/EXC3ll3NTrhyTHM/agent-workflow

## 1. Problem statement

Job hunting is a volume problem handled with human attention: the postings
worth applying to appear unpredictably across many boards, and finding them
means re-running the same searches and re-reading the same near-miss postings
every day. Job Scout inverts that: the candidate's résumé becomes the standing
search criteria, an agent scans remote-job boards nightly, scores every posting
against the résumé with an LLM, and emails the candidate only when something
genuinely strong appears. The goal is **passive, high-signal discovery** — the
user does nothing after setup, and an email from the system means "worth your
attention tonight."

Explicit non-goal: the system never applies to jobs or submits the résumé
anywhere on the user's behalf.

## 2. System overview

```
             ┌────────────────────────── nightly cron (07:30) ─────────────────────────┐
             │                                                                         │
 résumé ──▶ derive query ──▶ search corpus ──▶ score vs résumé ──▶ enough good matches?│
 (PDF/md)     (Claude)      (5 feeds, local)      (Claude)          │yes         │no   │
             │                   ▲                                  ▼            ▼     │
             │                   └── refine query (Claude), ◀── alert ≥8    2 dead     │
             │                       never repeat a query      + pitch      rounds? ──▶ stop,
             │                                                 (email)              report scarcity
             └─────────────────────────────────────────────────────────────────────────┘
   weekly cron (Sun 17:00): job-scout --digest — everything ≥6.5 since last digest, from SQLite only
```

The agent is a deliberately small but genuine agent loop (`src/job_scout/agent.py`):

- **Perceive** — derive a job-board query from the résumé (Claude), search the
  aggregated corpus, score each new posting 0–10 against the résumé (Claude).
- **Act** — decide per posting: instant email alert (score ≥ 8, deduplicated so
  a posting never alerts twice), weekly-digest material (≥ 6.5), or list-only.
  Each alerted posting gets three Claude-drafted "why I'm a fit" bullets
  grounded in the résumé.
- **Remember** — SQLite persists every scored posting, every tried query, and
  alert state across nightly runs; the loop never repeats a query.
- **Self-correct** — if a round yields fewer than 3 postings scoring ≥ 7, the
  agent derives a fresh query and tries again (up to 3 rounds); if two
  consecutive queries surface nothing new, it concludes the corpus has nothing
  for this résumé today and stops, reporting scarcity honestly.

### Components

| Piece | File(s) | Notes |
|---|---|---|
| Agent loop | `agent.py` | Plain Python; control flow is linear enough that a framework would obscure it |
| Tools | `tools.py` | `search_jobs`, `score_jobs`, `derive_query`, `draft_pitch` — each a plain function; every Claude tool has a deterministic, labelled fallback |
| Job corpus | `jobs.py` + 5 source clients | We Work Remotely, RemoteOK, Jobicy, Working Nomads, Remotive (~700 unique postings), merged, deduplicated, searched client-side |
| LLM access | `claude_cli.py` | Shells out to the `claude` CLI; no auth code in the app — the binary manages its own credential |
| State | `db.py` (SQLite) | Ranked listings, tried queries, alert dedup, digest window; additive migrations |
| Notifications | `alerts.py` | Instant alerts + weekly digest via Gmail SMTP; dry-run mode without credentials |
| Scheduling | `scripts/install_cron.sh` | Nightly scan + weekly digest on a home server; launchd variant for laptops |
| Evaluation | `evaluation.py`, `scripts/run_eval.py` | 12-case suite with an independent LLM judge (§4) |

### Design decisions that mattered

1. **Client-side search over a merged corpus.** Remotive's search API was
   discovered (Week 4) to be serving a stale CDN cache that ignores the query —
   verified via the `age` response header and identical job ids across
   different queries. Rather than depend on any one board's search, Job Scout
   pulls full feeds from five sources and filters locally, so the agent's
   query refinement stays meaningful and any single dead source degrades
   gracefully instead of breaking the run.
2. **Claude via the CLI subprocess, not an SDK.** The app contains zero
   credential-handling code; the `claude` binary authenticates itself. The
   pipeline runs identically on a laptop and under cron on the home server.
3. **Honest fallbacks.** Every Claude-backed tool has a deterministic fallback
   (keyword scoring, keyword query extraction) that is *labelled* — a result
   carries `source: "claude" | "fallback"` so degraded runs are never silently
   presented as model output. The fallback also doubles as the evaluation's
   no-LLM baseline.
4. **Two notification tiers.** An 8+ instant alert (calibrated in Week 4:
   integer scores drift ±1 run-to-run, so a 9 bar misses borderline-excellent
   jobs on unlucky days) and a weekly ≥6.5 digest that catches the
   worth-a-look band without spamming the inbox nightly.

## 3. What was built, week by week

| Week | Milestone |
|---|---|
| 3 | Core pipeline: résumé → query derivation → search → Claude scoring → ranked list; fixture suite; offline tests |
| 4 | Midpoint demo: email alerts with dedup; multi-source corpus after diagnosing Remotive's broken search; score-stability measurement (mean drift ≈ 1 point) |
| 5 | The agent runs itself: cron scheduling on a home server, instant alerts with Claude-drafted pitches, weekly digest tier |
| 6 | Evaluation: 12-case suite, LLM judge with failure taxonomy, three-arm comparison (full / no-refinement / no-Claude), results in `docs/eval/` |
| 7 | Acted on the eval: corpus ×3, honest scarcity handling, hopelessness-aware stop rule; re-ran the suite to measure the delta (§5) |

## 4. Evaluation methodology

(Condensed from `docs/evaluation.md`, which has the full detail.)

**Test set.** 12 cases in `tests/eval_cases.json`: 10 realistic profiles
(backend, frontend, data analyst, DevOps/SRE, ML, mobile, security, data
engineer, QA, product manager), 1 coverage probe (technical writer — a role
thin in the corpus), 1 edge case (career-changer with weak professional
signal). Each case is a résumé fixture plus a hand-written relevance rubric.

**Arms.** Each case runs three ways: **full** (the real agent), **round1**
(the run truncated to its first round — isolates the refinement loop's value),
and **fallback** (Claude disabled, all tools on their deterministic fallbacks —
isolates LLM judgment's value).

**Judging.** The agent's scorer cannot grade its own homework. An independent
LLM judge applies each case's rubric as a binary relevant/not-relevant call per
surfaced posting, with a failure category for misses (wrong-role-family,
adjacent-stack, seniority-mismatch, too-generic, non-engineering). Judge and
scorer prompts share no text. A 30-judgment manual spot-check agreed 28/30,
with both disagreements being strict calls (they lower the agent's measured
numbers, not raise them).

**Metrics** (per Track 3 guidance): task success (≥3 of top-5 judged relevant),
precision@5, step efficiency (rounds used, early-stop rate), and error
recovery (of cases where round 1 wasn't enough, how many refinement rescued).

## 5. Results

### Week 6: the diagnosis

On the original 241-posting corpus the full agent scored 2/12 task success,
mean P@5 0.32 — but feasibility analysis showed **10 of 12 cases had fewer
than 3 relevant postings in the entire corpus** (the technical-writer probe
had zero). On the 2 feasible cases the agent went 2/2. Conditioning on
feasibility flipped the conclusion: the agent's judgment was fine; **corpus
supply was the binding constraint**. Secondary findings, in priority order:

1. Padding: on no-match queries, search fell back to the head of the corpus
   and the scorer graded adjacent roles 6–9, so infeasible cases produced a
   confident wrong top-5 instead of an honest "nothing today"
   (wrong-role-family = 18 of 41 top-5 misses).
2. The stop rule could detect success but not hopelessness: 2.8 mean rounds,
   8% early-stop, ~6 wasted Claude calls per hopeless run.
3. Claude scoring beat keyword fallback on ranking (P@5 0.32 vs 0.20) and won
   hard discriminations (product_manager 0.60 vs 0.20), while the refinement
   loop added little (+0.05 P@5) — not wrong, just starved of supply.

### Week 7: the fixes

Each fix maps to a numbered finding above:

1. **Corpus ×3** — added We Work Remotely (main + 7 category RSS feeds,
   ~450 postings) and Working Nomads (~40) to the existing three sources:
   241 → ~710 unique postings.
2. **Honest scarcity** — `jobs.search` now returns an empty list when nothing
   matches instead of padding with the head of the corpus; the scoring prompt
   is calibrated ("different role family caps at 3; 7+ means could credibly
   apply today"); the CLI says "nothing scored 7+ today" instead of dressing
   up weak matches.
3. **Hopelessness-aware stop** — the agent stops (`stop_reason="exhausted"`)
   when two consecutive queries surface nothing new, or when two full rounds
   produce not a single good match. (A stricter "no increase in good matches"
   rule was considered and rejected against the data: python_backend plateaued
   at 2 good matches for two rounds, then found its third in round 3.)
   Postings already scored in a previous round are also never re-scored — each
   re-surfaced posting previously cost scorer budget every round it reappeared.

Also fixed along the way: unstable fallback job ids (Python's per-process
`hash()` would have broken cross-run alert dedup for sources without numeric
ids — replaced with a stable digest), and two dead dependencies (`langgraph`,
`pydantic`) removed for a lighter fresh-clone install.

### Week 7: the re-run

Same 12 cases, same judge, same metrics; corpus snapshot at run time:
**710 postings** (run of 2026-07-25).

| Arm | Task success | Mean P@5 | Mean rounds | Early-stop | Error recovery |
|---|---|---|---|---|---|
| full (Wk 6 → Wk 7) | 2/12 → **8/12 (67%)** | 0.32 → **0.65** | 2.8 → 2.1 | 8% → 67% | 1/11 → 5/9 |
| round1 | 2/12 → 7/12 | 0.27 → 0.55 | 1.0 | — | — |
| fallback | 1/12 → 7/12 | 0.20 → 0.48 | 3.0 → 2.0 | — | — |

Reading the delta against the Week 6 diagnosis:

- **The supply fix did exactly what the eval predicted.** Feasible cases
  (≥3 relevant postings existed among everything surfaced) went from 2 to 8,
  and the agent passed **8 of 8** — extending its Week 6 record of passing
  every passable case. Five cases that were mathematically unwinnable last
  week now PASS, four of them at P@5 1.00.
- **Every remaining failure is a supply failure, not a judgment failure.** The
  four fails (mobile_dev, data_engineer, technical_writer, career_changer) had
  1, 1, 0 and 2 relevant postings respectively in the whole 710-posting
  corpus — and in each case the agent's top-5 contained *every relevant
  posting that existed*. Precision@5 misses are now entirely "the corpus
  didn't stock it," never "the agent ranked it wrong."
- **The stop rule now detects hopelessness.** Early-stop rate rose from 8% to
  67% and mean rounds fell 2.8 → 2.1. The new zero-good-after-two-rounds rule
  fired on exactly the cases it was designed for (mobile_dev,
  technical_writer — both stopped at round 2 rather than burning a third).
  data_engineer and career_changer correctly kept hunting: each had found one
  good match early, so the search was not yet provably hopeless.
- **The agentic parts still earn their keep, more visibly than before.** Full
  agent beats the no-refinement ablation on success (8 vs 7) and P@5 (0.65 vs
  0.55), and refinement rescued 5 of 9 rounds-1-insufficient cases (Week 6:
  1 of 11 — the loop was never broken, it was starved). Claude scoring beats
  keyword fallback 0.65 vs 0.48 on P@5. Notably the *fallback* baseline also
  improved (1/12 → 7/12) — most of the headline gain was supply, which is
  precisely the Week 6 conclusion ("supply before smarts") validated by
  intervention.

## 6. Limitations and threats to validity

- **LLM-as-judge**: judge and scorer are both Claude models; a shared blind
  spot would inflate scores. Mitigated by disjoint prompts, hand-written
  per-case rubrics, and the manual spot-check — not eliminated.
- **Live corpus**: feeds change daily, so exact numbers are snapshots; the
  corpus size is recorded in each results file. The comparison *between* arms
  is more stable than any absolute number, since all arms share each case's
  verdicts.
- **Score drift**: Claude's integer scores drift ±1 run-to-run (measured Week
  4), so borderline pass/fail can flip between runs.
- **Single-host state**: alert dedup lives in one SQLite file; running the
  schedule on two hosts would double-alert. Deliberately out of scope.
- **English remote-tech bias**: all five feeds skew English-language,
  remote, tech-adjacent. A non-tech résumé gets honest scarcity reporting now,
  but the fix for coverage is more/better sources, not agent changes.

## 7. Lessons learned

1. **Evaluate before optimizing — the eval reversed my priorities.** Before
   Week 6 the obvious next steps looked like prompt and loop improvements. The
   eval showed the loop was fine and *supply* was the constraint; the
   highest-leverage fix was adding RSS feeds, not anything agentic.
2. **Feasibility-condition the metrics.** A 17% success rate said "broken
   agent"; conditioning on whether success was possible at all said "starved
   agent, sound judgment." Without the feasibility cut I would have spent
   Week 7 fixing the wrong thing.
3. **Design the failure path as carefully as the success path.** The worst
   behavior found all project was the system *confidently padding* — every
   layer (search fallback, curve-grading scorer, top-5 display) individually
   chose "always return something," and the composition produced polished
   nonsense. "No results" needs to be a first-class outcome.
4. **Independent judging is non-negotiable.** The scorer thought its padded
   top-5s were 6–9/10; the judge (with rubrics) called 18 of 41 wrong-family.
   Self-graded metrics would have shown a healthy system.
5. **Boring infrastructure choices paid off.** Plain Python loop over a
   framework, subprocess CLI over SDK auth code, SQLite over anything
   fancier — every one of these made the system easier to run under cron,
   test offline, and demo.

## 8. Future work

- Per-profile source selection (the corpus is tech-heavy; a technical-writer
  résumé deserves writing-focused feeds).
- Re-score drift dampening: keep a rolling average per posting instead of
  last-write-wins.
- The optional Track 3 stretch goals — resume-upload web UI and a chat
  interface over stored postings — remain unbuilt; the agent + notifications
  core took priority.

## Appendix A: How to run

See README → Quickstart. Short version: `python3 -m venv .venv`,
`.venv/bin/pip install -e ".[dev]"`, copy `.env.example` → `.env` (set
`CLAUDE_PATH`, `RESUME_PATH`), then `.venv/bin/job-scout resume.pdf`.
Tests: `.venv/bin/python -m pytest tests/` (offline, no Claude needed).
Evaluation: `PYTHONPATH=src .venv/bin/python scripts/run_eval.py`.

## Appendix B: Evidence index

- `docs/evaluation.md` — full evaluation methodology + Week 6 results
- `docs/eval/results.md`, `docs/eval/results.json` — current-run tables and raw judgments
- `docs/week-4-midpoint.md` — Remotive CDN diagnosis, score-stability data
- `docs/week-{3..7}-report.md` — weekly progress reports
