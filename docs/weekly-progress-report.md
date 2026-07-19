# Week 5 Progress Report

Name: Blake Simpson  Week: 5 (Advanced Workflow) Track: Track 3 — Agent

## What I did this week

I made the agent run itself: two launchd agents now drive it on a schedule — a nightly scan (07:30) and a weekly digest (Sunday 17:00) — installed by `scripts/install_launchd.sh` with logs in `logs/`. I split notifications into two tiers: instant alerts (≥ 8) work as before, and the new `job-scout --digest` emails a weekly recap of everything scored ≥ 6.5 since the last digest, split into "already alerted" and "worth a look — never tripped an alert." I added a fourth agent tool, `draft_pitch`, which writes three "why I'm a fit" bullets grounded strictly in my résumé for each fresh alert, includes them in the alert email, and stores them in the DB. I also wrote the project's first real test suite — 9 offline pytest tests with a fake SMTP server and a mocked Claude — and verified the whole thing end to end on my real résumé with `EMAIL_DRY_RUN=1`.

## What worked

- The digest's very first dry-run against my real database was immediately useful: it surfaced three 7.0 jobs (Nebius, A.Team, Mitre Media) that I had never been alerted about because they sat below the instant threshold. The two-tier design earned its keep before it even shipped.
- The pitch prompt ("use ONLY facts present in the résumé") produced surprisingly specific output on the first try — it cited my on-prem LLM deployment, the genetic prompt-optimization work, and H100 orchestration for the NTT DATA GenAI role, with nothing invented.
- The live SQLite database migrated in place (new `meta` table + `pitch` column) with zero manual steps — the additive-migration approach meant Week 4's data just kept working.

## What Failed or Surprised me

- Writing the first tests immediately found a real bug: `EMAIL_DRY_RUN` had been documented in the Week 4 docstring but the code never actually checked it — the docstring promised behavior that didn't exist. Four weeks of manual testing never caught this; the first afternoon of automated testing did.
- The launchd environment bites exactly the way my own Week 2 deployment notes predicted: launchd's minimal PATH can't find a bare `claude`, and `.env` only loads if the working directory is the repo. The fix was baking the absolute `CLAUDE_PATH` into the plist and setting `WorkingDirectory` — the code changes for scheduling were trivial, the environment plumbing was the whole job.
- I went in planning "a cron job" and came out with launchd instead: cron silently skips any run whose time passes while the laptop is asleep, which for an overnight job on a laptop is most runs. launchd fires the missed job once on wake.

## What I learned

- Threshold tuning was the wrong frame all along. Weeks 3–4 I kept lowering one threshold (9 → 8.5 → 8) trying to make a single number both spam-free and complete. Two tiers dissolve the tension: the instant bar can stay strict because the weekly digest catches the 6.5–8 band anyway.
- Scheduled execution is a different environment, not a different feature. Everything interactive I took for granted — PATH, HOME, working directory, credentials — has to be made explicit, and dedup/idempotency stops being a nicety and becomes the thing that makes unattended runs safe.
- Order of operations controls cost in an agent pipeline: pitches are drafted only *after* alert dedup, so a nightly run never spends Claude calls re-pitching jobs it already emailed about.

## Evidence of Progress

- Commit: https://github.com/EXC3ll3NTrhyTHM/agent-workflow/commit/6133b8d
- New code: `scripts/install_launchd.sh`, `scripts/uninstall_launchd.sh`, `tools.draft_pitch`, `alerts.send_digest`, `tests/test_workflow.py` (9 tests, all passing)
- Schedule is live: `launchctl list | grep jobscout` shows both agents loaded (`com.jobscout.scan`, `com.jobscout.digest`)
- Sample from the live end-to-end run (dry-run mode; the dedup skipped the already-alerted Lemon.io job and pitched only the fresh one):

```
2 alert-worthy (>= 8.0):
   8.0  GenAI Engineer  @ NTT DATA
   8.0  Senior AI Engineer  @ Lemon.io
  drafting pitch for GenAI Engineer @ NTT DATA (Claude, ~10-30s)...

Subject: Job Scout: 1 strong match(es) — top: GenAI Engineer @ NTT DATA
8.0/10  GenAI Engineer @ NTT DATA
        why: GenAI engineering directly matches LLM integration, prompt
        engineering, and on-prem model deployment experience.
        your pitch:
        - As Lead Full Stack AI Engineer at T-Mobile, they already design,
          build, and deploy enterprise AI solutions — including an on-premise
          open-source LLM optimized with a genetic prompt-optimization
          algorithm ...
```

- Sample from the first weekly digest (dry-run against the real DB):

```
Subject: Job Scout weekly digest: 6 match(es), 3 you haven't been alerted about
== Already alerted instantly (3) ==
9.0/10  Senior AI Engineer Architect @ Lemon.io
...
== Worth a look — never tripped an instant alert (3) ==
7.0/10  Senior ML Engineer (Token Factory) @ Nebius
...
```

## Plan for Next week

- Build the Week 6 eval harness: 20 test tasks (résumé profiles + expected relevance criteria) and a scoring rubric, run the agent against all of them.
- Watch the first week of unattended scheduled runs in `logs/scan.log` — the NTT DATA job is queued to send the first real scheduled alert (with pitch) at the next 07:30 run.
- Check digest quality after the first real Sunday send; if the 6.5 floor lets junk in, raise it before touching anything else.

## Blockers

- None
