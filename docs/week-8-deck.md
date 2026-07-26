---
marp: true
theme: default
paginate: true
---

<!-- Week 8 presentation deck — renders as slides with Marp
     (VS Code: install "Marp for VS Code", open this file, click preview).
     Each `---` is a slide break; speaker notes are in HTML comments. -->

# Job Scout Agent

### An agent that hunts jobs while you sleep

Blake Simpson · Track 3 — Agent
github.com/EXC3ll3NTrhyTHM/agent-workflow

---

## The problem

- The good postings appear unpredictably, across many boards, and go fast
- Manual job hunting = re-running the same searches every day and re-reading the same near-misses
- Most "job alert" emails are keyword matches — high volume, low signal

**Goal: passive, high-signal discovery.**
Your résumé is the standing search. An email from the system means *worth your attention tonight*.

<!-- Note: non-goal — it never applies on your behalf. -->

---

## What it does

Every night at 07:30 (cron, home server):

1. Derives a job-board query from your résumé *(Claude)*
2. Searches a ~700-posting corpus merged from 5 public feeds
3. Scores each new posting 0–10 against your résumé *(Claude)*
4. **Score ≥ 8** → instant email, with 3 "why I'm a fit" bullets grounded in your résumé
5. Not enough good matches → refines the query and tries again

Sundays: a digest email of the 6.5–8 "worth a look" band.

---

## A small but genuine agent

| Agent property | In Job Scout |
|---|---|
| **Perceives** | search + LLM scoring of each posting |
| **Acts** | alert / digest / list-only decision per posting |
| **Remembers** | SQLite: every tried query, every score, alert dedup |
| **Self-corrects** | derives a fresh query when a round comes up thin — never repeats one |
| **Knows when to stop** | enough good matches, *or* two dead-end queries in a row |

Plain Python loop — no framework. Claude via the `claude` CLI subprocess — zero auth code in the app.

---

## War story: the job board that lied

- Week 4: every Remotive query returned **identical results**
- Diagnosis via the `age` response header: a stale CDN cache ignoring the search param entirely
- Fix: stop trusting any single board's search — pull **full feeds from 5 sources**, merge, dedupe, search client-side

The agent's query refinement stays meaningful, and one dead source degrades the corpus instead of breaking the run.

---

## Evaluating an agent honestly

**12 cases** (`tests/eval_cases.json`): 10 realistic profiles + a coverage probe + a career-changer edge case — each with a hand-written relevance rubric.

**3 arms per case** — full agent · round-1 only (is refinement worth it?) · Claude disabled (is the LLM worth it?)

**Independent LLM judge** applies each rubric per posting — the scorer never grades its own homework. Manual spot-check: 28/30 agreement.

Metrics: task success (≥3 relevant in top-5), precision@5, step efficiency, error recovery.

---

## Week 6: the number that lied

# 17% task success 😱

…but **10 of 12 cases had < 3 relevant postings in the entire 241-posting corpus.** Success was mathematically impossible.

On the 2 feasible cases: **the agent went 2/2.**

> The agent's judgment was fine. **Corpus supply was the constraint.**

<!-- Note: this is the core story — evaluation reversed the priorities. -->

---

## Week 6 also caught: confident padding

When nothing matched, every layer chose "return something anyway":

- search fell back to head-of-corpus
- the scorer graded on a curve (adjacent roles got 6–9)
- the top-5 always looked full and confident

Result: **wrong-role-family = 18 of 41 top-5 misses.**
And the stop rule burned all 3 rounds (~6 Claude calls) on hopeless corpora.

---

## Week 7: fix what the eval measured

| Eval finding | Fix |
|---|---|
| Supply is the constraint | +We Work Remotely (8 feeds) +Working Nomads → **241 → ~710 postings** |
| Confident padding | Search returns honest empties; scorer calibrated (wrong role family caps at 3); CLI says "nothing scored 7+ today" |
| Can't detect hopelessness | Stop on 2 dead-end queries in a row, or zero good matches after 2 rounds; never re-score a seen posting |

---

## Did it work? Same 12 cases, re-run

| Metric | Week 6 | Week 7 |
|---|---|---|
| Task success (full agent) | 2/12 | **8/12** |
| Mean precision@5 | 0.32 | **0.65** |
| Success on *feasible* cases | 2/2 | **8/8** |
| Early-stop rate / mean rounds | 8% / 2.8 | **67%** / 2.1 |
| vs. keyword baseline P@5 | 0.20 | 0.48 |

All 4 remaining fails had ≤2 relevant postings **in the entire 710-posting corpus** — and the agent's top-5 contained every one that existed.

<!-- Note: misses are now purely "the corpus didn't stock it," never
     "the agent ranked it wrong." -->


---

## Lessons learned

1. **Evaluate before optimizing** — the eval reversed my roadmap: the fix was RSS feeds, not smarter prompts
2. **Condition metrics on feasibility** — 17% meant "starved," not "broken"
3. **Design the failure path** — "no results today" must be a first-class outcome, or the system pads
4. **Never let the scorer grade itself** — self-graded metrics would have shown a healthy system
5. **Boring choices compound** — plain loop, subprocess auth, SQLite: everything runs under cron and tests offline

---

## Demo: one success, one failure

**Success** — `job-scout resume.pdf`, live: watch it derive a query, search,
score, refine, stop at 3 good matches → the alert email with pitch bullets

**Failure** — the technical-writer résumé, live: zero relevant postings exist →
*"nothing scored 7+ today"*, stops after 2 rounds instead of pretending

An agent you can trust is one that can come back empty-handed.

**Questions?**

<!-- ============================================================
FINAL DEMO RUN-OF-SHOW — 8 min demo + 4 min Q&A (not a slide)

0:00–0:45  Framing: résumé in, email out, nothing in between (slide 3).
0:45–4:00  SUCCESS CASE, LIVE: job-scout with my real résumé.
           Narrate the loop during Claude latency (corpus warm-up
           ~15s first). While it runs, flip to the architecture
           slide. Finish on the terminal's ranked list, then the
           alert email screenshot (score + reasoning + 3 pitch
           bullets).
4:00–6:00  FAILURE CASE, LIVE:
           job-scout tests/fixtures/resume_technical_writer.md
           — honest scarcity: "nothing scored 7+ today", exhausted
           stop at round 2. Say the slide's last line out loud.
6:00–7:30  The eval story, fast: 17% → feasibility cut → 3 fixes →
           before/after table (slides 7-10).
7:30–8:00  Lessons slide, one breath each. Land on "evaluate before
           optimizing."

SAFETY NET: keep a second terminal with a completed run of both
cases scrolled and ready in case wifi/Claude stalls.
Set EMAIL_DRY_RUN=1 for the live runs so no real email fires
mid-demo.

Q&A backup talking points:
- Remotive CDN war story (slide 5)
- Why no framework: plain loop, linear control flow, easier to
  test offline and run under cron
- Judge validity: disjoint prompts, hand-written rubrics, 28/30
  manual spot-check agreement
- Cost per scan: ~4-6 Claude calls; already-seen postings are
  never re-scored
============================================================ -->
