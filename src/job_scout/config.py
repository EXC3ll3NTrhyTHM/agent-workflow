"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # Claude access is via the `claude` CLI subprocess (see claude_cli.py).
    model: str | None  # passed to `claude --model`; None => CLI default
    claude_path: str | None  # absolute path to the binary (required under cron/systemd)
    claude_home: str | None  # HOME override so the CLI finds the right ~/.claude
    # Matching. 8 rather than a hard 9: scores are integers and drift by ±1
    # run-to-run, so a 9.0 bar makes borderline-excellent jobs alert only on
    # lucky days (see docs/week-4-midpoint.md, Failure 3).
    alert_threshold: float
    # Weekly digest covers everything from this floor up — the 6.5-8 band that
    # is worth a look but never trips an instant alert.
    digest_floor: float
    # Gmail SMTP
    gmail_address: str
    gmail_app_password: str
    alert_recipient: str
    # Paths
    resume_path: str
    db_path: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            model=os.environ.get("JOB_SCOUT_MODEL") or None,
            claude_path=os.environ.get("CLAUDE_PATH") or None,
            claude_home=os.environ.get("CLAUDE_HOME") or None,
            alert_threshold=float(os.environ.get("ALERT_THRESHOLD", "8")),
            digest_floor=float(os.environ.get("DIGEST_FLOOR", "6.5")),
            gmail_address=os.environ.get("GMAIL_ADDRESS", ""),
            gmail_app_password=os.environ.get("GMAIL_APP_PASSWORD", ""),
            alert_recipient=os.environ.get("ALERT_RECIPIENT", ""),
            resume_path=os.environ.get("RESUME_PATH", "data/resume.pdf"),
            db_path=os.environ.get("DB_PATH", "data/job_scout.db"),
        )
