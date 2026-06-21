"""Week 1 setup check: confirm the data source and Claude are reachable.

Run:  python scripts/verify_setup.py

- Remotive API is public (no key) and should pass if you have internet.
- Claude is reached via the `claude` CLI subprocess (same auth model as the
  tmobile-scout app): the binary authenticates itself from
  ~/.claude/.credentials.json (after `claude login`) or ANTHROPIC_API_KEY.
  If the CLI isn't installed / logged in here, the check is skipped, not failed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Make `job_scout` importable without installing the package first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

load_dotenv()


def check_remotive() -> bool:
    print("[1/2] Remotive API (job data) ...")
    try:
        import requests

        resp = requests.get(
            "https://remotive.com/api/remote-jobs", params={"limit": 1}, timeout=30
        )
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])
        sample = jobs[0]["title"] if jobs else "(no jobs returned)"
        print(f"      OK — reachable. Sample posting: {sample!r}")
        return True
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        print(f"      FAIL — {exc}")
        return False


def check_claude() -> bool:
    print("[2/2] Claude CLI (subprocess auth) ...")
    try:
        from job_scout import claude_cli
    except ImportError as exc:
        print(f"      SKIP — package not importable ({exc})")
        return True

    # Is the binary even here? (It runs on your server; may be absent locally.)
    try:
        path = claude_cli.resolve_claude_path(os.environ.get("CLAUDE_PATH"))
    except claude_cli.ClaudeError as exc:
        print(f"      SKIP — {exc}")
        return True

    home = os.environ.get("CLAUDE_HOME")
    print(f"      binary: {path}")

    try:
        reply = claude_cli.run_claude(
            "Reply with exactly: pong",
            claude_path=path,
            home=home,
            model=os.environ.get("JOB_SCOUT_MODEL") or None,
            timeout=120,
        )
        print(f"      OK — Claude replied: {reply.splitlines()[0][:60]!r}")
        return True
    except claude_cli.ClaudeRateLimitError as exc:
        print(f"      WARN — auth works but rate-limited/out of quota: {exc}")
        return True
    except claude_cli.ClaudeAuthError as exc:
        if claude_cli.has_credentials(home):
            print(f"      FAIL — credential present but Claude rejected it: {exc}")
            return False
        print("      SKIP — no Claude credential on this machine.")
        print("             Run `claude login` here once (or set ANTHROPIC_API_KEY).")
        return True
    except claude_cli.ClaudeError as exc:
        print(f"      FAIL — {exc}")
        return False


def main() -> int:
    print("Job Scout Agent — setup verification\n")
    results = [check_remotive(), check_claude()]
    print()
    if all(results):
        print("All checks passed (or skipped). You're ready for Week 3.")
        return 0
    print("Some checks failed — see messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
