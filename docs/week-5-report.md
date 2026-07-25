# Week 5 Progress Report

Name: Blake Simpson  Week: 5 (Advanced Workflow) Track: Track 3 — Agent

## What I did this week

The agent now runs on a nightly schedule starting at 7:30am and sends out a weekly digest on my home server on Sundays at 5pm. 

Additionally I added another agent tool that will write why it sees that Im a fit for the role that it suggests with a bulleted list grounded in my resume for each alert, and stores then draft pitches in the DB.

## What worked

- The digest's very first dry-run against my real database was immediately useful: it surfaced three 7.0 jobs (Nebius, A.Team, Mitre Media) that I had never been alerted about because they sat below the instant threshold. The two-tier design earned its keep before it even shipped.
- The scheduling install worked on the first run: one script loads both launchd agents, and `launchctl` confirms them waiting on their calendar triggers. To be clear about what's verified vs. pending: the pipeline passed a full manual end-to-end run under the same entry point the schedule invokes, but the first truly unattended run is tomorrow 07:30; next week's report gets the log evidence.
- The pitch prompt ("use ONLY facts present in the résumé") produced surprisingly specific output on the first try. It cited my on-prem LLM deployment, the genetic prompt-optimization work, and H100 orchestration for the NTT DATA GenAI role, with nothing invented.
- The live SQLite database migrated in place (new `meta` table + `pitch` column) with zero manual steps — the additive-migration approach meant Week 4's data just kept working.

## What Failed or Surprised me

- The launchd environment got hung up exactly the way my Week 2 deployment notes predicted: launchd's minimal PATH can't find a bare `claude`, and `.env` only loads if the working directory is the repo. The fix was baking the absolute `CLAUDE_PATH` into the plist and setting `WorkingDirectory`.

## What I learned

- Scheduled execution is a different environment, not a different feature. Everything interactive I took for granted — PATH, HOME, working directory, and credentials have to be made explicit.
- Order of operations controls cost in an agent pipeline: pitches are drafted only after alert dedup, so a nightly run never spends Claude calls re-pitching jobs it already emailed about.

## Evidence of Progress

- Commit: https://github.com/EXC3ll3NTrhyTHM/agent-workflow/commit/6133b8d
- New code: `scripts/install_launchd.sh`, `scripts/uninstall_launchd.sh`, `tools.draft_pitch`, `alerts.send_digest`, `tests/test_workflow.py` (9 tests, all passing)
- Schedule is live: `launchctl list | grep jobscout` shows both agents loaded (`com.jobscout.scan`, `com.jobscout.digest`)
- Sample from the live end-to-end run (dry-run mode; the dedup skipped the already-alerted Lemon.io job and pitched only the fresh one):

## Plan for Next week

- Build the Week 6 eval harness: 20 test tasks (résumé profiles + expected relevance criteria) and a scoring rubric, run the agent against all of them.
- Watch the first week of unattended scheduled runs in `logs/scan.log` — the NTT DATA job is queued to send the first real scheduled alert (with pitch) at the next 07:30 run.
- Check digest quality after the first real Sunday send; if the 6.5 floor lets junk in, raise it before touching anything else.

## Blockers

- None
