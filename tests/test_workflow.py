"""Offline tests for the Week 5 workflow pieces: DB migration, the weekly
digest, and pitch drafting. No network, no Claude, no real SMTP — Claude is
monkeypatched and email sends are captured by a fake SMTP class.

Run with: .venv/bin/python -m pytest tests/
"""

from __future__ import annotations

import sqlite3

import pytest

from job_scout import alerts, db, tools
from job_scout.config import Config
from job_scout.remotive import Job
from job_scout.tools import ScoredJob


def make_config(**overrides) -> Config:
    defaults = dict(
        model=None, claude_path=None, claude_home=None,
        alert_threshold=8.0, digest_floor=6.5,
        gmail_address="scout@example.com", gmail_app_password="app-pass",
        alert_recipient="me@example.com",
        resume_path="data/resume.pdf", db_path=":memory:",
    )
    defaults.update(overrides)
    return Config(**defaults)


def make_job(job_id: int, title: str = "Backend Engineer") -> Job:
    return Job(
        id=job_id, title=title, company=f"Co{job_id}", category="software-dev",
        url=f"https://example.com/{job_id}", location="Remote",
        description="<p>Python, APIs, SQL.</p>",
    )


def insert_job(conn, job_id: int, score: float, *, alerted: int = 0,
               first_seen: str | None = None) -> None:
    db.upsert_job(
        conn, job_id=job_id, title=f"Job {job_id}", company=f"Co{job_id}",
        url=f"https://example.com/{job_id}", score=score, reasoning="because",
    )
    if alerted:
        db.mark_alerted(conn, job_id)
    if first_seen:
        conn.execute(
            "UPDATE jobs SET first_seen = ? WHERE id = ?", (first_seen, job_id)
        )


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL; records the messages it 'sends'."""

    sent: list = []

    def __init__(self, host, port):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(alerts.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


# --------------------------------------------------------------------------- #
# DB: migration + meta + digest window
# --------------------------------------------------------------------------- #
def test_migrates_legacy_db(tmp_path):
    """A Week-4 DB (no pitch column, no meta table) upgrades in place."""
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(path)
    legacy.execute(
        "CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
        "company TEXT NOT NULL, url TEXT NOT NULL, score REAL NOT NULL, "
        "reasoning TEXT, alerted INTEGER NOT NULL DEFAULT 0, "
        "first_seen TEXT NOT NULL DEFAULT (datetime('now')), "
        "last_scored TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    legacy.execute(
        "INSERT INTO jobs (id, title, company, url, score) "
        "VALUES (1, 'T', 'C', 'u', 9.0)"
    )
    legacy.commit()
    legacy.close()

    with db.connect(path) as conn:
        db.set_pitch(conn, 1, "- fits well")
        assert conn.execute("SELECT pitch FROM jobs WHERE id = 1").fetchone()[0] \
            == "- fits well"
        db.set_meta(conn, "last_digest_at", "2026-07-01 00:00:00")
        assert db.get_meta(conn, "last_digest_at") == "2026-07-01 00:00:00"


def test_jobs_for_digest_windows_on_first_seen(tmp_path):
    with db.connect(tmp_path / "t.db") as conn:
        insert_job(conn, 1, 9.0, first_seen="2026-07-01 00:00:00")
        insert_job(conn, 2, 7.0, first_seen="2026-07-10 00:00:00")
        insert_job(conn, 3, 5.0, first_seen="2026-07-10 00:00:00")  # below floor

        everything = db.jobs_for_digest(conn, since=None, floor=6.5)
        assert [r["id"] for r in everything] == [1, 2]  # score desc, no floor-miss

        windowed = db.jobs_for_digest(conn, since="2026-07-05 00:00:00", floor=6.5)
        assert [r["id"] for r in windowed] == [2]


# --------------------------------------------------------------------------- #
# Weekly digest
# --------------------------------------------------------------------------- #
def test_send_digest_sends_and_advances_window(tmp_path, smtp):
    cfg = make_config()
    with db.connect(tmp_path / "t.db") as conn:
        insert_job(conn, 1, 9.0, alerted=1)
        insert_job(conn, 2, 7.0)

        rows = alerts.send_digest(cfg, conn, dry_run=False)
        assert [r["id"] for r in rows] == [1, 2]
        assert len(smtp.sent) == 1
        body = smtp.sent[0].get_content()
        assert "Already alerted instantly (1)" in body
        assert "never tripped an instant alert (1)" in body
        assert db.get_meta(conn, "last_digest_at") is not None

        # Nothing new since the digest => quiet week, no second email.
        assert alerts.send_digest(cfg, conn, dry_run=False) == []
        assert len(smtp.sent) == 1


def test_send_digest_dry_run_keeps_window_open(tmp_path, smtp, capsys):
    cfg = make_config()
    with db.connect(tmp_path / "t.db") as conn:
        insert_job(conn, 1, 7.5)
        rows = alerts.send_digest(cfg, conn, dry_run=True)
        assert len(rows) == 1
        assert smtp.sent == []
        assert "dry run" in capsys.readouterr().out
        # The window did not advance, so a later real run still covers job 1.
        assert db.get_meta(conn, "last_digest_at") is None


def test_email_dry_run_env_forces_dry_run(tmp_path, smtp, monkeypatch):
    monkeypatch.setenv("EMAIL_DRY_RUN", "1")
    cfg = make_config()
    with db.connect(tmp_path / "t.db") as conn:
        insert_job(conn, 1, 7.5)
        alerts.send_digest(cfg, conn)  # dry_run inferred from the env
    assert smtp.sent == []


# --------------------------------------------------------------------------- #
# Instant alerts with pitches
# --------------------------------------------------------------------------- #
def test_send_alerts_includes_pitch_for_fresh_jobs_only(tmp_path, smtp):
    cfg = make_config()
    scored = [
        ScoredJob(make_job(1), 9.0, "great fit", "claude"),
        ScoredJob(make_job(2), 8.5, "good fit", "claude"),
    ]
    pitched: list[int] = []

    def pitch_for(s: ScoredJob) -> str | None:
        pitched.append(s.job.id)
        return "- overlap one\n- overlap two\n- overlap three"

    with db.connect(tmp_path / "t.db") as conn:
        insert_job(conn, 2, 8.5, alerted=1)  # already alerted => no pitch, no email row
        fresh = alerts.send_alerts(cfg, scored, conn, dry_run=False,
                                   pitch_for=pitch_for)

    assert [s.job.id for s in fresh] == [1]
    assert pitched == [1]  # pitch drafted only after dedup
    body = smtp.sent[0].get_content()
    assert "your pitch:" in body
    assert "- overlap two" in body


def test_send_alerts_none_pitch_omits_section(smtp):
    cfg = make_config()
    scored = [ScoredJob(make_job(1), 9.0, "great fit", "claude")]
    alerts.send_alerts(cfg, scored, None, dry_run=False, pitch_for=lambda s: None)
    assert "your pitch:" not in smtp.sent[0].get_content()


# --------------------------------------------------------------------------- #
# Pitch tool
# --------------------------------------------------------------------------- #
def test_draft_pitch_parses_bullets(monkeypatch):
    monkeypatch.setattr(
        tools.claude_cli, "run_claude",
        lambda *a, **k: '{"bullets": ["Python overlap", "API experience", "SQL"]}',
    )
    pitch = tools.draft_pitch("résumé text", make_job(1))
    assert pitch == "- Python overlap\n- API experience\n- SQL"


def test_draft_pitch_returns_none_when_claude_unavailable(monkeypatch):
    def boom(*a, **k):
        raise tools.claude_cli.ClaudeError("down")

    monkeypatch.setattr(tools.claude_cli, "run_claude", boom)
    assert tools.draft_pitch("résumé text", make_job(1)) is None
