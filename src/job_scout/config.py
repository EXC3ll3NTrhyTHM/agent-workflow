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
    # Matching
    alert_threshold: int
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
            alert_threshold=int(os.environ.get("ALERT_THRESHOLD", "9")),
            gmail_address=os.environ.get("GMAIL_ADDRESS", ""),
            gmail_app_password=os.environ.get("GMAIL_APP_PASSWORD", ""),
            alert_recipient=os.environ.get("ALERT_RECIPIENT", ""),
            resume_path=os.environ.get("RESUME_PATH", "data/resume.pdf"),
            db_path=os.environ.get("DB_PATH", "data/job_scout.db"),
        )
