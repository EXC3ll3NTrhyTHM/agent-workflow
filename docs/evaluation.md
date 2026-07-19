# Week 6 — Evaluation of the Job Scout Agent

Track 3 (Agent). This document is the evaluation section of the final report:
methodology, quantitative results, a comparison against two baselines/ablations,
and a qualitative failure analysis.

## 1. What is being evaluated

The Job Scout agent takes a résumé and autonomously finds matching remote-job
postings: it derives a search query with Claude, searches a three-source job
corpus (RemoteOK + Jobicy + Remotive), scores each posting against the résumé
with Claude (0–10), and — when a round produces fewer than 3 postings scoring
≥7 — refines the query and searches again, up to 3 rounds.

The evaluation question: **does the agent actually surface relevant jobs, and
do its agentic parts (LLM scoring, the refinement loop) earn their keep?**

## 2. Test set (12 cases)

`tests/eval_cases.json` defines 12 test cases, each a résumé fixture plus an
explicit relevance rubric (what counts as relevant for this profile, and what
near-misses do not). Ten are realistic distinct profiles — Python backend,
React frontend, data analyst, DevOps/SRE, ML engineer, mobile, security, data
engineer, QA automation, product manager — one is a coverage probe (technical
writer, a role thin in the corpus), and one is a deliberate edge case (a
career-changer résumé with weak professional signal, mostly teaching
experience).

## 3. Method

Three arms run per case:

| Arm | What it is | What it isolates |
|---|---|---|
| **full** | The real agent: Claude scorer + up to 3 refinement rounds | — |
| **round1** | The full run truncated to its first round | Value of the refinement loop |
| **fallback** | The agent with Claude disabled: keyword-derived query, keyword-overlap scorer | Value of LLM judgment vs. keyword matching |

The round1 arm is reconstructed from the full run's per-round logs (no extra
cost); the fallback arm is a real run with `claude_path` pointed at a
nonexistent binary, which drives every tool down its deterministic fallback
path.

**Judging.** The agent's own scorer cannot grade the agent. Every posting any
arm surfaced is judged once per case by an LLM judge applying that case's
rubric as a binary relevant/not-relevant decision, with a failure category for
the misses (taxonomy: wrong-role-family, adjacent-stack, seniority-mismatch,
too-generic, non-engineering, other). The judge prompt shares no text with the
scoring prompt, judges against explicit hand-written criteria rather than
holistic fit, and postings the judge skips are counted *not* relevant. All
three arms are graded from the same verdict set, and I manually spot-checked
judgments (§6).

**Metrics** (Track 3 guidance):

- **Task success rate** — a case passes when ≥3 of the arm's top-5 postings are
  judged relevant. The bar mirrors the agent's own target ("3 good matches")
  but is measured with the independent judge.
- **Precision@5** — judged-relevant fraction of the top 5.
- **Step efficiency** — rounds used (of 3 allowed) and early-stop rate: does
  the agent know when to stop?
- **Error recovery rate** — among cases where round 1 alone was insufficient
  (the agent's own `n_good < 3` trigger), the fraction the refinement loop
  rescued to a judged task success.

Reproduce with: `PYTHONPATH=src .venv/bin/python scripts/run_eval.py`
(full details land in `docs/eval/results.json`, summary in `docs/eval/results.md`).

## 4. Quantitative results

Run of 2026-07-19; corpus snapshot: 241 unique postings across the three
sources. Full per-case table in `docs/eval/results.md`, raw judgments in
`docs/eval/results.json`.

| Arm | Task success | Mean P@5 | Mean rounds (of 3) | Early-stop rate | Error recovery |
|---|---|---|---|---|---|
| **full** (the agent) | **2/12 (17%)** | **0.32** | 2.8 | 8% | 1/11 |
| round1 (no refinement) | 2/12 (17%) | 0.27 | 1.0 | — | — |
| fallback (no Claude) | 1/12 (8%) | 0.20 | 3.0 | 0% | — |

The headline 17% looks damning until you condition on feasibility. For each
case, count how many judged-relevant postings *existed at all* among everything
any arm surfaced: **10 of 12 cases had fewer than 3** — task success was
mathematically impossible for any system on those cases that day (the
technical-writer probe had zero relevant postings in the entire corpus).
Restricted to the 2 feasible cases (devops_sre, product_manager):

| Arm | Success on feasible cases |
|---|---|
| full | **2/2** |
| round1 | 2/2 |
| fallback | 1/2 |

So the agent passed every case that was passable, and the binding constraint is
**corpus supply, not agent judgment**. The 241-posting corpus (originally a
workaround for Remotive's broken search) simply doesn't stock 3+ postings for
most specific profiles on a given day.

Secondary comparisons:

- **Claude scoring earns its keep on ranking**: mean P@5 0.32 vs 0.20 for the
  keyword fallback, and on the feasible product_manager case the difference is
  stark (0.60 vs 0.20 — keyword overlap can't tell a PM role from a
  product-adjacent engineering role).
- **The refinement loop adds little**: +0.05 mean P@5 over round1 and no extra
  task successes. Error recovery was 1/11 — but 10 of those 11 "round 1 wasn't
  enough" situations were infeasible cases, where no query can rescue the run.
  The one feasible opportunity (product_manager) *was* recovered. The loop
  isn't wrong, it's starved.
- **Step efficiency is poor on infeasible cases**: the agent early-stopped only
  once (8%) and averaged 2.8 rounds because its stop rule can only detect
  success, not hopelessness — it burns all 3 rounds (≈6 Claude calls, ~70–150s
  wall) re-querying a corpus that doesn't contain what it needs. Tracing calls
  for this metric also exposed a genuine waste: `run_agent` derived a
  next-round query even on the final round, one Claude call per full-length run
  whose result was discarded. Fixed this week.

## 5. Qualitative analysis

**Failure taxonomy** (judge categories over the full arm's top-5 misses, 41
postings across 12 cases):

| Category | Count | What it looks like |
|---|---|---|
| wrong-role-family | 18 | A QA lead surfaced for the data-engineer résumé |
| adjacent-stack | 9 | DevOps roles scored 7–9 for the ML engineer |
| too-generic | 5 | "Senior Software Engineer" postings too vague to establish fit |
| seniority-mismatch | 5 | Engineering-manager roles for IC résumés; senior roles for the junior |
| non-engineering | 4 | A digital-media/marketing role for the career-changer |

The common thread: **the agent never returns empty-handed, even when it
should.** Two design choices compound — `jobs.search` falls back to the head of
the corpus when nothing matches the query, and the scorer grades on a curve,
handing 6s and 7s to adjacent roles when nothing genuinely fits. The result is
a confident-looking top-5 stuffed with wrong-family postings instead of an
honest "found 1 real match today."

**Case studies:**

1. *devops_sre — the keyword baseline beat the agent (P@5 0.80 vs 0.60).* Both
   arms found the same relevant SRE/DevOps postings, but Claude ranked a
   generic "Senior Software Engineer" posting above a fourth relevant DevOps
   role; dumb keyword overlap kept the DevOps roles adjacent to a DevOps
   résumé. Same adjacent-stack inflation as above, seen from the other side —
   LLM scoring wins on hard discrimination (product_manager) and loses
   occasionally on easy cases it overthinks.
2. *technical_writer — clean supply failure, not a search failure.* The three
   derived queries were exactly right ("technical writer API documentation",
   "developer documentation writer", "documentation engineer openapi"); the
   corpus contained zero relevant postings. Score 0.00 across all arms. This is
   the case that proves the metric distinguishes "agent failed" from "task was
   impossible."
3. *career_changer (edge case) — graceful degradation.* The agent's #1 pick was
   the single relevant posting in the corpus (a Junior Software Engineer role),
   and its misses were near-misses (Junior QA Tester, React Native). With thin,
   mixed-signal input the agent found the one right answer, then padded —
   again, the padding is the failure mode, not the finding.

## 6. Judge validity spot-check

I re-read 30 of the ~350 judgments across four cases (ml_engineer,
devops_sre, product_manager, career_changer) against the postings. Agreement:
28/30. The two I'd argue with are both *strict* calls, not lenient ones —
"ML Engineering Manager, Ads Modeling" ruled seniority-mismatch for the IC ML
résumé (defensible; the résumé says nothing about managing), and "React Native
Engineer" ruled adjacent-stack for the career-changer (they list some React).
Since both disputed calls lower the agent's measured scores, the reported
numbers are conservative rather than flattered.

## 7. Threats to validity

- **LLM-as-judge**: the judge is a Claude model, as is the scorer; a shared
  blind spot would inflate scores. Mitigated (not eliminated) by disjoint
  prompts, per-case hand-written rubrics, and the manual spot-check in §6.
- **Round-1 reconstruction**: postings first seen in round 1 keep their best
  score across rounds, so the round1 arm's ranking can be slightly generous.
  This biases *against* the headline claim (it makes the refinement loop look
  less necessary), so it is safe.
- **Live corpus**: the job feeds change daily; exact numbers are a snapshot.
  The corpus size at run time is recorded in the results file.
- **Single run per case**: Claude scoring drifts run-to-run (measured in Week
  4's `score_stability.py`: mean drift ≈1 point). Success/failure on borderline
  cases could flip on a re-run; the comparison between arms is more stable
  because all arms share each case's judged verdicts.

## 8. What the evaluation changes

Ranked by measured impact:

1. **Supply before smarts.** Nothing about scoring or refinement matters until
   the corpus stocks enough postings per profile. More sources / larger feed
   pulls is the highest-leverage next step (10 of 12 cases were unwinnable).
2. **Let the agent give up.** Add an infeasibility signal to the stop rule
   (e.g., stop if a round's best *judged-by-scorer* score falls below the good
   bar twice running) instead of burning all 3 rounds on empty corpora.
3. **Stop padding the top-5.** Suppress the head-of-corpus search fallback and
   surface "1 real match today" honestly — every padded slot in an alert email
   is trust spent.
4. (Done this week) the wasted final-round `derive_query` call is removed.
