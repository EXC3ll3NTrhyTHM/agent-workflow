# Job Scout Agent

An AI agent that reads an uploaded résumé and searches the web for jobs that match it — ranking each posting against your experience and emailing you when something is a strong fit.

> **Course Project — Track 3: Agent**

## Overview

The job market is competitive, and manually scanning job boards is slow and repetitive. Job Scout Agent automates the search: it uses your résumé as the search criteria, queries job boards on a schedule, ranks every posting by how well it matches you, and surfaces the best ones. When a posting is an exceptional match (8/10 or higher), it sends you an email alert so you can review and apply.

If a search doesn't return enough good results, the agent adjusts its own search criteria and tries again — while remembering which queries it has already run so it doesn't repeat itself.

## Who It's For

Job seekers who want **passive, high-signal** job discovery: good-quality matches delivered to them, with the ability to tune the search criteria, instead of doom-scrolling job boards.

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│   Résumé    │────▶│  Search jobs │────▶│  Rank each    │────▶│  Decision:   │
│  (uploaded) │     │ (multi-source│     │  posting vs.  │     │  email alert │
│             │     │  corpus)     │     │  résumé (LLM) │     │  or list only│
└─────────────┘     └──────────────┘     └───────────────┘     └──────────────┘
                           ▲                                            │
                           │      not enough good results?              │
                           └────────────────────────────────────────────┘
                              adjust criteria, avoid repeating queries
```

The scan workflow runs nightly (07:30, scheduled on the home server):

1. **Query** the aggregated job corpus (RemoteOK + Jobicy + Remotive feeds, searched client-side) for remote postings.
2. **Rank** each posting against the résumé with an LLM, producing a 0–10 match score.
3. **Decide** per posting: if the score is ≥ 8, send an email alert (deduped — never twice for the same posting); otherwise add it to the ranked listing.
4. **Pitch**: for each posting that makes the alert email, the LLM drafts three
   "why I'm a fit" bullets grounded in the résumé, included in the email.
5. **Refine** if results are insufficient: adjust the search criteria and re-query, tracking already-tried queries to avoid repeats.

A second, cheaper workflow runs weekly (Sunday 17:00): `job-scout --digest`
emails a recap of everything scored ≥ 6.5 since the last digest — the
instant alerts you already got, plus the borderline "worth a look" matches
that never tripped one. It reads only the SQLite state (no scanning, no LLM).

### Scheduling

The intended host is an always-on home server, scheduled with cron:

```sh
./scripts/install_cron.sh       # nightly scan + weekly digest as cron jobs
crontab -l | grep -v '# job-scout' | crontab -   # remove them
```

For running on a laptop instead, use the launchd variant — cron silently
skips runs whose time passes while the machine is asleep, launchd fires
them on wake:

```sh
./scripts/install_launchd.sh    # macOS laptop alternative
./scripts/uninstall_launchd.sh  # remove both agents
```

Either way, logs go to `logs/scan.log` and `logs/digest.log`. Run on ONE
host only: dedup state lives in the host's own SQLite file, so two hosts
send duplicate alerts.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Agent orchestration | [LangGraph](https://langchain-ai.github.io/langgraph/) |
| Backend | Python |
| LLM | [Claude](https://www.anthropic.com/claude), called via the `claude` CLI (Claude Code) as a subprocess |
| Job data | [RemoteOK](https://remoteok.com/api) + [Jobicy](https://jobicy.com/jobs-rss-feed) + [Remotive](https://remotive.com/api/remote-jobs) feeds (public, no auth), merged and searched client-side |
| State | SQLite (tried queries, alerted jobs, ranked listings) |
| Email | Gmail SMTP |
| Résumé | Local file uploaded by the user (PDF or plain text / Markdown) |

## Authentication

There is **no auth code in this app.** It shells out to the `claude` CLI
(Claude Code) and lets the binary authenticate itself — exactly how it's done in
the existing tmobile-scout app. The credential lives in one file the CLI manages
(`~/.claude/.credentials.json`, an OAuth token from `claude login` that the CLI
auto-refreshes). This process never sees, stores, or transmits it.

So "set up auth" = make sure the binary is reachable and a credential exists:

1. **Install Claude Code** and run `claude login` once on the host (writes the
   credentials file). The CLI refreshes the token automatically after that.
2. **Set `CLAUDE_PATH`** to the binary's absolute path (`which claude`). This is
   required under cron/systemd, whose minimal PATH won't find a bare `claude`.
3. **Run as a user who can read that `~/.claude`** — or set `CLAUDE_HOME` to
   point at it. (The #1 "works in my terminal, fails in the service" cause is a
   service running as a different user with no `~/.claude`.)

**Headless / container alternative:** set `ANTHROPIC_API_KEY` instead — the same
`claude` binary uses the key (pay-per-token), no `claude login` needed.

Verify the setup on any host: `python scripts/verify_setup.py`

## Scope

### Will build

1. Take a résumé and search job boards for matching jobs.
2. Rank jobs by how well they match the résumé.
3. Send email alerts for strong matches.
4. *(Optional)* Web UI to upload a résumé and view the ranked list.
5. *(Optional)* Chatbot to ask questions about the job postings.

### Will not build

- An app that submits applications or résumés on the user's behalf.

## Roadmap

| Weeks | Goal |
|-------|------|
| 1–2 | Setup and background |
| 3 | UI: upload a résumé, view ranked job list |
| 4 | Email notifications for good matches |
| 5 | Chatbot to ask questions about postings |
| 6 | Write 20 test tasks (résumé profiles + expected relevance criteria); run agent against them |
| 7–8 | Polish, report, demo |

## Risks

| Risk | Backup plan |
|------|-------------|
| LLM emails poor-match postings | Tune the model and improve prompts to raise match quality |

## Data & API Access

- **RemoteOK / Jobicy / Remotive APIs** — public, no authentication required.
- **Gmail SMTP** — public server; requires app credentials to be configured
  (`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `ALERT_RECIPIENT`; without them the
  alert step runs in dry-run mode and prints the email instead of sending).
- **Résumé** — local file provided by the user.

## Status

🚧 Week 5: the agent now runs itself. Nightly scheduled scan + instant alerts
with LLM-drafted "why I'm a fit" pitches, and a weekly digest
(`job-scout --digest`) covering the borderline matches (≥ 6.5) that never
tripped an instant alert. Run a scan with `job-scout` (or
`python scripts/run_baseline.py` for the fixture suite); tests in `tests/`
run offline with `pytest`.

Earlier: Week 4 midpoint — résumé → search → score → ranked list → email alert,
end to end.
Job data comes from a three-source corpus (RemoteOK + Jobicy + Remotive)
filtered client-side, after Remotive's own search API was found to be serving a
stale CDN cache that ignores the query — see `docs/week-4-midpoint.md` for the
midpoint evidence (recall before/after, score-stability results) and
`docs/weekly-progress-report.md` for the Week 3 write-up.
