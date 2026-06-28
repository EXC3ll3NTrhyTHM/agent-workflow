"""Console entry point (`job-scout`): run the agent on one résumé and print the
ranked job list plus any alert-worthy matches.

Usage:
    job-scout                 # uses RESUME_PATH from .env / config
    job-scout path/to/cv.md   # score against a specific résumé file
"""

from __future__ import annotations

import sys

from .agent import run_agent
from .config import Config
from .resume import load_resume


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = Config.from_env()
    resume_path = argv[0] if argv else cfg.resume_path

    try:
        resume_text = load_resume(resume_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Could not load résumé: {exc}", file=sys.stderr)
        return 1

    print(f"Job Scout — scoring against {resume_path}\n")
    result = run_agent(
        resume_text,
        resume_label=resume_path,
        db_path=cfg.db_path,
        alert_threshold=float(cfg.alert_threshold),
        claude_path=cfg.claude_path,
        home=cfg.claude_home,
        model=cfg.model,
    )

    print(f"Tried queries: {', '.join(result.tried_queries)}")
    print(f"Postings seen: {len(result.scored)}\n")
    print("Top matches:")
    for s in result.scored[:10]:
        print(f"  {s.score:4.1f}  {s.job.title}  @ {s.job.company}  [{s.source}]")
        print(f"        {s.job.url}")

    if result.alerts:
        print(f"\n{len(result.alerts)} alert-worthy (>= {cfg.alert_threshold}):")
        for s in result.alerts:
            print(f"  {s.score:4.1f}  {s.job.title}  @ {s.job.company}")
    else:
        print(f"\nNo postings reached the alert threshold ({cfg.alert_threshold}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
