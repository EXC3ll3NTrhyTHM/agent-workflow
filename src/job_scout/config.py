"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    model: str
    alert_threshold: int
    gmail_address: str
    gmail_app_password: str
    alert_recipient: str
    resume_path: str
    db_path: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            model=os.environ.get("JOB_SCOUT_MODEL", "claude-opus-4-8"),
            alert_threshold=int(os.environ.get("ALERT_THRESHOLD", "9")),
            gmail_address=os.environ.get("GMAIL_ADDRESS", ""),
            gmail_app_password=os.environ.get("GMAIL_APP_PASSWORD", ""),
            alert_recipient=os.environ.get("ALERT_RECIPIENT", ""),
            resume_path=os.environ.get("RESUME_PATH", "data/resume.pdf"),
            db_path=os.environ.get("DB_PATH", "data/job_scout.db"),
        )
