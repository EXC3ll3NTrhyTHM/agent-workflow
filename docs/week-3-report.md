# Week 3 Progress Report

Name: Blake Simpson Week: 3 (Baseline Prototype) Track: Track 3 — Agent

## What I did this week

I finished the prototype for the agent so that it runs end to end, so the Remotive/RemoteOK client, the Claude CLI wrapper, SQLite, and the resume loader.

Created:

- Tools layer (`src/job_scout/tools.py`) - this defines the actions the agent can take: search_jobs, score_jobs and derive_query.
- The Agent Loop (`src/job_scout/agent.py`) - search → score → decide → refine. Remembers queries it has tried and if a round doesnt find enough good matches(3 results that are rated 7/10) it derives a different query and goes again. After 3 retries it gives up.
- Entry point (`src/job_scout/main.py`)
- 5 test tasks - résumé fixtures in `tests/fixtures/` (Python backend, React Frontend, ML engineer, DevOps/SRE, data analyst) and a runner (`scripts/run_baseline.py`) that runs the agent on all five and records the outputs to `docs/baseline_outputs.md`.

## What worked

- It runs end to end on all 5 tests using Remotive and live Claude. outputs are here `docs/baseline_outputs.md`.
- Claude scoring works and makes sense.
- The agentic loop behaves as it should.
- The fallback for if Claude isnt working works as well

## What Failed or Surprised me

- The Remotive public api is currently ignoring my search query. No matter what I put in the remotive query it returned the same 33 postings. This was determined to be a cached set that was being served.

## How I resolved the Remotive Issue

- Cache busting techniques didnt work so instead I added a different source RemoteOK and combined it with the Remotive results. RemoteOK is giving relevant jobs and allowed the agent to correctly rank the relevant jobs.

## What I learned

- How to structure an agent with tools and a loop with memory.
- Batching the LLM calls to save tokens. Can use one CLaude call for scoring all the postings.
- Always give deterministic fallback for exiting loop and if the LLM is unreachable
- Verify the data source returns relevant jobs, not just that it works.

## Evidence of Progress

- Baseline outputs for all 5 test tasks: `docs/baseline_outputs.md`
- New code: src/job_scout/tools.py , src/job_scout/agent.py ,src/job_scout/main.py , src/job_scout/remoteok.py , src/job_scout/jobs.py , tests/fixtures/resume_*.md , scripts/run_baseline.py .
- Run it: python scripts/run_baseline.py (or job-scout <résumé> for one).
- Repo: https://github.com/EXC3ll3NTrhyTHM/agent-workflow
Sample (ML-engineer test task, multi-source corpus + Claude scoring):
- 9.0 Senior Independent AI Engineer / Architect [claude] strong senior remote LLM/ML
- 3.0 Tech Lead Full-Stack Rails Engineer [claude] senior but Rails, not ML fo
- 1.0 Senior Product Manager [claude] not an ML engineering role
tried: machine learning engineer llm, nlp rag engineer

## Plan for Next week

- Troubleshoot Remotive API further and determine if it should be removed from data sources.
- Build Email-alert step
- Start score-stability check - run the same resume twice and measure score drift

## Blockers

- None