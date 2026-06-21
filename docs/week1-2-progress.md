# Progress Report — Weeks 1–2 (Setup & Background)

**Project:** Job Scout Agent — Track 3 (Agent)
**Repo:** https://github.com/EXC3ll3NTrhyTHM/agent-workflow

## This week's goal
Set up the development environment, confirm data/API access, read just enough
background, and push an initial commit with the folder structure and README.

## What I did

### 1. Dev environment
- Python virtual environment (`.venv`), Python 3.11+ (verified on 3.14).
- Installed core libraries: `anthropic`, `langgraph` (1.2.6), `requests`,
  `pydantic`, `pypdf`, `python-dotenv`. All import cleanly.
- Project is an installable package (`pyproject.toml`, `src/` layout) with a
  `job-scout` console entry point reserved for later.
- Secrets handled via `.env` (gitignored); `.env.example` documents every key.

### 2. Data / API access — verified
- **Remotive API** (job postings): public, no auth. `scripts/verify_setup.py`
  pulls live postings successfully — e.g. *"Senior Independent AI Engineer /
  Architect"*. ✅ Working.
- **Claude (Anthropic) API**: chosen as the LLM (latest model, native LangGraph
  support, strong at structured scoring). Verification script has a live
  ping-test; it currently **SKIPs** because the API key isn't installed yet.
  → **Action item:** add `ANTHROPIC_API_KEY` to `.env` and re-run the check.
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
- **LLM:** Claude (`claude-opus-4-8`) instead of the originally-proposed OpenAI.
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
