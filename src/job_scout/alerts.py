"""Email alerts: notify when a posting scores at/above the alert threshold.

One digest email per run (not one per job) via Gmail SMTP, using an app
password from config. Two safeguards:

- Dedup: postings already alerted on (``db.has_been_alerted``) are skipped, so
  a daily run never re-sends the same job.
- Dry-run: if Gmail credentials are missing — or ``EMAIL_DRY_RUN`` is set —
  the composed email is printed instead of sent, and nothing is marked
  alerted. This keeps the pipeline runnable (and demoable) without secrets.
"""

from __future__ import annotations

import smtplib
import sqlite3
from email.message import EmailMessage

from . import db
from .config import Config
from .tools import ScoredJob

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465  # SSL


def send_alerts(
    cfg: Config,
    alerts: list[ScoredJob],
    conn: sqlite3.Connection | None = None,
    *,
    dry_run: bool | None = None,
) -> list[ScoredJob]:
    """Send one digest email for the not-yet-alerted postings in `alerts`.

    Returns the postings actually included in the email (empty if none were
    new). When `dry_run` is None it is inferred: missing Gmail credentials =>
    dry-run. In dry-run mode the email is printed, not sent, and postings are
    NOT marked alerted, so a real run later still notifies."""
    fresh = [
        s for s in alerts
        if conn is None or not db.has_been_alerted(conn, s.job.id)
    ]
    if not fresh:
        return []

    if dry_run is None:
        dry_run = not (cfg.gmail_address and cfg.gmail_app_password)
    recipient = cfg.alert_recipient or cfg.gmail_address
    msg = _build_digest(fresh, sender=cfg.gmail_address, recipient=recipient)

    if dry_run:
        print("\n--- email alert (dry run — set GMAIL_ADDRESS / GMAIL_APP_PASSWORD to send) ---")
        print(f"To: {recipient or '<no recipient configured>'}")
        print(f"Subject: {msg['Subject']}")
        print(msg.get_content())
        print("--- end dry run ---")
        return fresh

    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as smtp:
        smtp.login(cfg.gmail_address, cfg.gmail_app_password)
        smtp.send_message(msg)
    if conn is not None:
        for s in fresh:
            db.mark_alerted(conn, s.job.id)
    return fresh


def _build_digest(alerts: list[ScoredJob], *, sender: str, recipient: str) -> EmailMessage:
    top = max(alerts, key=lambda s: s.score)
    lines = []
    for s in sorted(alerts, key=lambda s: s.score, reverse=True):
        lines.append(f"{s.score:.1f}/10  {s.job.title} @ {s.job.company}")
        if s.reasoning:
            lines.append(f"        why: {s.reasoning}")
        lines.append(f"        {s.job.url}")
        lines.append("")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = (
        f"Job Scout: {len(alerts)} strong match(es) — "
        f"top: {top.job.title} @ {top.job.company}"
    )
    msg.set_content(
        "Job Scout found new postings at or above your alert threshold:\n\n"
        + "\n".join(lines)
    )
    return msg
