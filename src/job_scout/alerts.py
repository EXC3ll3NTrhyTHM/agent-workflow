"""Email notifications, in two tiers.

- **Instant alerts** (`send_alerts`): one email per run covering postings at/
  above the alert threshold, sent the night the agent finds them. Each fresh
  posting can carry a Claude-drafted "why I'm a fit" pitch.
- **Weekly digest** (`send_digest`): one email per week summarising everything
  at/above the (lower) digest floor since the last digest — the borderline
  matches that never tripped an instant alert, plus a recap of the ones that
  did.

Both go via Gmail SMTP with an app password from config, and share two
safeguards:

- Dedup: instant alerts skip postings already alerted on
  (``db.has_been_alerted``); the digest windows on ``first_seen`` since the
  ``last_digest_at`` timestamp it records in the DB.
- Dry-run: if Gmail credentials are missing — or ``EMAIL_DRY_RUN`` is set —
  the composed email is printed instead of sent, and no dedup state is
  recorded. This keeps the pipeline runnable (and demoable) without secrets.
"""

from __future__ import annotations

import os
import smtplib
import sqlite3
from email.message import EmailMessage
from typing import Callable

from . import db
from .config import Config
from .tools import ScoredJob

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465  # SSL

_LAST_DIGEST_KEY = "last_digest_at"


def _resolve_dry_run(cfg: Config, dry_run: bool | None) -> bool:
    if dry_run is not None:
        return dry_run
    if os.environ.get("EMAIL_DRY_RUN"):
        return True
    return not (cfg.gmail_address and cfg.gmail_app_password)


def _deliver(cfg: Config, msg: EmailMessage, *, dry_run: bool, kind: str) -> bool:
    """Send `msg`, or print it in dry-run mode. Returns True if actually sent."""
    if dry_run:
        print(f"\n--- {kind} (dry run — set GMAIL_ADDRESS / GMAIL_APP_PASSWORD to send) ---")
        print(f"To: {msg['To'] or '<no recipient configured>'}")
        print(f"Subject: {msg['Subject']}")
        print(msg.get_content())
        print("--- end dry run ---")
        return False
    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as smtp:
        smtp.login(cfg.gmail_address, cfg.gmail_app_password)
        smtp.send_message(msg)
    return True


def send_alerts(
    cfg: Config,
    alerts: list[ScoredJob],
    conn: sqlite3.Connection | None = None,
    *,
    dry_run: bool | None = None,
    pitch_for: Callable[[ScoredJob], str | None] | None = None,
) -> list[ScoredJob]:
    """Send one instant-alert email for the not-yet-alerted postings in `alerts`.

    Returns the postings actually included in the email (empty if none were
    new). When `dry_run` is None it is inferred: missing Gmail credentials =>
    dry-run. In dry-run mode the email is printed, not sent, and postings are
    NOT marked alerted, so a real run later still notifies.

    `pitch_for` is called once per fresh posting (only after dedup, so pitches
    are never drafted for jobs that won't be emailed); a None pitch simply
    omits that section."""
    fresh = [
        s for s in alerts
        if conn is None or not db.has_been_alerted(conn, s.job.id)
    ]
    if not fresh:
        return []

    dry_run = _resolve_dry_run(cfg, dry_run)
    recipient = cfg.alert_recipient or cfg.gmail_address
    pitches = {s.job.id: pitch_for(s) for s in fresh} if pitch_for else {}
    msg = _build_alert_email(
        fresh, pitches=pitches, sender=cfg.gmail_address, recipient=recipient
    )

    sent = _deliver(cfg, msg, dry_run=dry_run, kind="email alert")
    if sent and conn is not None:
        for s in fresh:
            db.mark_alerted(conn, s.job.id)
    return fresh


def _build_alert_email(
    alerts: list[ScoredJob],
    *,
    pitches: dict[int, str | None],
    sender: str,
    recipient: str,
) -> EmailMessage:
    top = max(alerts, key=lambda s: s.score)
    lines = []
    for s in sorted(alerts, key=lambda s: s.score, reverse=True):
        lines.append(f"{s.score:.1f}/10  {s.job.title} @ {s.job.company}")
        if s.reasoning:
            lines.append(f"        why: {s.reasoning}")
        pitch = pitches.get(s.job.id)
        if pitch:
            lines.append("        your pitch:")
            lines.extend(f"        {line}" for line in pitch.splitlines())
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


def send_digest(
    cfg: Config,
    conn: sqlite3.Connection,
    *,
    floor: float | None = None,
    dry_run: bool | None = None,
) -> list[sqlite3.Row]:
    """Send the weekly digest: every posting at/above `floor` first seen since
    the last digest, split into the ones that already triggered an instant
    alert and the borderline ones that didn't.

    Returns the rows covered (empty => quiet week, no email). Reads only the
    DB — no scanning, no Claude — so it's cheap enough to run on any schedule.
    `last_digest_at` advances only when an email is actually sent; a quiet or
    dry-run week just widens the next digest's window."""
    floor = cfg.digest_floor if floor is None else floor
    since = db.get_meta(conn, _LAST_DIGEST_KEY)
    rows = db.jobs_for_digest(conn, since=since, floor=floor)
    if not rows:
        print(f"Digest: nothing new at/above {floor} since "
              f"{since or 'the beginning'} — no email.")
        return []

    dry_run = _resolve_dry_run(cfg, dry_run)
    recipient = cfg.alert_recipient or cfg.gmail_address
    msg = _build_digest_email(
        rows, floor=floor, since=since,
        sender=cfg.gmail_address, recipient=recipient,
    )

    if _deliver(cfg, msg, dry_run=dry_run, kind="weekly digest"):
        db.set_meta(conn, _LAST_DIGEST_KEY, db.utcnow(conn))
    return rows


def _build_digest_email(
    rows: list[sqlite3.Row],
    *,
    floor: float,
    since: str | None,
    sender: str,
    recipient: str,
) -> EmailMessage:
    alerted = [r for r in rows if r["alerted"]]
    worth_a_look = [r for r in rows if not r["alerted"]]

    def _section(title: str, entries: list[sqlite3.Row]) -> list[str]:
        if not entries:
            return []
        lines = [title, ""]
        for r in entries:
            lines.append(f"{r['score']:.1f}/10  {r['title']} @ {r['company']}")
            if r["reasoning"]:
                lines.append(f"        why: {r['reasoning']}")
            lines.append(f"        {r['url']}")
            lines.append("")
        return lines

    window = f"since {since} (UTC)" if since else "all time (first digest)"
    body = [
        f"Job Scout weekly digest — {len(rows)} match(es) at/above {floor:g}, "
        f"{window}.",
        "",
        *_section(f"== Already alerted instantly ({len(alerted)}) ==", alerted),
        *_section(
            f"== Worth a look — never tripped an instant alert "
            f"({len(worth_a_look)}) ==",
            worth_a_look,
        ),
    ]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = (
        f"Job Scout weekly digest: {len(rows)} match(es), "
        f"{len(worth_a_look)} you haven't been alerted about"
    )
    msg.set_content("\n".join(body))
    return msg
