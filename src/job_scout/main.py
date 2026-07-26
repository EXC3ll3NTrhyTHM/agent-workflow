"""Console entry point (`job-scout`): run the agent on one résumé and print the
ranked job list plus any alert-worthy matches — or send the weekly digest.

Usage:
    job-scout                 # scan: uses RESUME_PATH from .env / config
    job-scout path/to/cv.md   # scan against a specific résumé file
    job-scout --digest        # weekly digest email from the DB (no scanning)
"""

from __future__ import annotations

import argparse
import sys

from . import alerts, db, tools
from .agent import run_agent
from .config import Config
from .resume import load_resume


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="job-scout",
        description="Scan job boards against a résumé, or send the weekly digest.",
    )
    parser.add_argument(
        "resume", nargs="?", default=None,
        help="résumé file to score against (default: RESUME_PATH from .env)",
    )
    parser.add_argument(
        "--digest", action="store_true",
        help="send the weekly digest of matches since the last digest, then exit "
             "(reads the DB only — no scanning, no Claude)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    cfg = Config.from_env()

    if args.digest:
        return _run_digest(cfg)
    return _run_scan(cfg, args.resume or cfg.resume_path)


def _run_digest(cfg: Config) -> int:
    print(f"Job Scout — weekly digest (floor {cfg.digest_floor:g})\n", flush=True)
    with db.connect(cfg.db_path) as conn:
        rows = alerts.send_digest(cfg, conn)
    if rows:
        print(f"Digest covered {len(rows)} match(es).")
    return 0


def _run_scan(cfg: Config, resume_path: str) -> int:
    try:
        resume_text = load_resume(resume_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Could not load résumé: {exc}", file=sys.stderr)
        return 1

    print(f"Job Scout — scoring against {resume_path}\n", flush=True)
    result = run_agent(
        resume_text,
        resume_label=resume_path,
        db_path=cfg.db_path,
        alert_threshold=float(cfg.alert_threshold),
        claude_path=cfg.claude_path,
        home=cfg.claude_home,
        model=cfg.model,
        verbose=True,
    )
    print()

    print(f"Tried queries: {', '.join(result.tried_queries)}")
    print(f"Postings seen: {len(result.scored)}\n")

    good = [s for s in result.scored if s.score >= 7.0]
    if not result.scored:
        print("No postings matched this résumé's queries at all — the job "
              "boards have nothing relevant right now. Try again tomorrow.")
    elif not good:
        # Be honest about scarcity rather than dressing up weak matches
        # (Week 6 eval: padding was the #2 failure mode).
        print("Nothing scored 7+ today — the closest postings are below, "
              "but none are a real match:")
    else:
        print("Top matches:")
    for s in result.scored[:10]:
        print(f"  {s.score:4.1f}  {s.job.title}  @ {s.job.company}  [{s.source}]")
        print(f"        {s.job.url}")
    if result.stop_reason == "exhausted":
        print("\n(search stopped early: repeated queries found nothing new "
              "in today's corpus)")

    if result.alerts:
        print(f"\n{len(result.alerts)} alert-worthy (>= {cfg.alert_threshold}):")
        for s in result.alerts:
            print(f"  {s.score:4.1f}  {s.job.title}  @ {s.job.company}")
        with db.connect(cfg.db_path) as conn:

            def pitch_for(s):
                print(f"  drafting pitch for {s.job.title} @ {s.job.company} "
                      "(Claude, ~10-30s)...", flush=True)
                pitch = tools.draft_pitch(
                    resume_text, s.job, claude_path=cfg.claude_path,
                    home=cfg.claude_home, model=cfg.model,
                )
                if pitch:
                    db.set_pitch(conn, s.job.id, pitch)
                return pitch

            sent = alerts.send_alerts(cfg, result.alerts, conn, pitch_for=pitch_for)
        if sent:
            print(f"\nEmail alert covered {len(sent)} new posting(s).")
        else:
            print("\nAll alert-worthy postings were already alerted on — no email.")
    else:
        print(f"\nNo postings reached the alert threshold ({cfg.alert_threshold}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
