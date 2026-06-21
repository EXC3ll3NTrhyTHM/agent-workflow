# Progress Report — Weeks 1–2 (Setup & Background)

**Project:** Job Scout Agent — Track 3 (Agent)
**Repo:** https://github.com/EXC3ll3NTrhyTHM/agent-workflow

## This week's goal
Set up the development environment, confirm data/API access, read just enough
background, and push an initial commit with the folder structure and README.

## What I did

### 1. Dev environment
- Python virtual environment (`.venv`), Python 3.11+ (verified on 3.14).
- Installed core libraries: `langgraph` (1.2.6), `requests`, `pydantic`,
  `pypdf`, `python-dotenv`. All import cleanly.
- Claude is reached via the `claude` CLI (Claude Code) as a subprocess — no SDK
  and no auth code in the app. The binary authenticates itself.
- Project is an installable package (`pyproject.toml`, `src/` layout) with a
  `job-scout` console entry point reserved for later.
- Secrets handled via `.env` (gitignored); `.env.example` documents every key.

### 2. Data / API access — verified
- **Remotive API** (job postings): public, no auth. `scripts/verify_setup.py`
  pulls live postings successfully — e.g. *"Senior Independent AI Engineer /
  Architect"*. ✅ Working.
- **Claude** (LLM for match scoring): integrated by shelling out to the `claude`
  CLI, which authenticates from `~/.claude/.credentials.json` (subscription
  login, auto-refreshed) — the same pattern as the existing tmobile-scout app.
  Verification ran live and Claude replied `pong`. ✅ Working, no API key needed.
  → **On the server (Zoidberg):** run `claude login` once and set `CLAUDE_PATH`
  to the absolute binary path so cron/systemd can find it.
- **Gmail SMTP** (email alerts): planned; credentials (App Password) to be set
  up in Week 4 when notifications are built.

Run the check anytime with: `python scripts/verify_setup.py`

### 3. Folder structure (initial commit)
```
agent-workflow/
├── README.md               # project skeleton / overview
├── pyproject.toml          # deps + packaging
├── .env.example            # documented config keys
├── scripts/verify_setup.py # data/API access check
├── src/job_scout/
│   ├── config.py           # env-based configuration
│   ├── claude_cli.py       # Claude via `claude` CLI subprocess (auth-free)
│   ├── resume.py           # load résumé from PDF or text/markdown
│   ├── remotive.py         # Remotive API client
│   └── db.py               # SQLite: ranked jobs, alert dedup, tried queries
├── docs/                   # progress reports
├── tests/                  # (to be filled in Week 6)
└── data/                   # local résumé + SQLite db (gitignored)
```

### 4. Background reading (Track 3 — Agent)
- Anthropic, *Building Effective Agents* — when to use workflows vs. agents.
- LangGraph docs — `StateGraph`, nodes/edges, conditional routing (the core of
  the "search → rank → decide → refine" loop).
- *(Skim)* ReAct (Yao et al.) — reasoning + acting loop, background for the
  agent's self-correcting query refinement.

## Key design decisions made this week
- **LLM:** Claude instead of the originally-proposed OpenAI.
- **Claude auth:** call the `claude` CLI as a subprocess (no SDK, no auth code),
  reusing the subscription login — mirrors the existing tmobile-scout app and
  keeps the project key-free on a personal server.
- **Persistence:** SQLite — needed so the agent remembers tried queries and
  doesn't re-alert on the same job between daily runs.
- **Résumé input:** accept both PDF and plain text / Markdown.

## Biggest unknown heading into Week 3
**Match-score consistency.** The plan emails on a hard "9/10 or higher"
threshold, but a single LLM score can drift run-to-run. Week 3 will test whether
a simple structured score is stable enough, or whether I need a more explicit
rubric / multi-criteria scoring to make the threshold meaningful.

## Next week (Week 3)
Build the résumé-upload + ranked-list flow: load a résumé, query Remotive, score
each posting with Claude, and persist the ranked list to SQLite.
