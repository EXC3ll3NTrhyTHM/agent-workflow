"""Week 1 setup check: confirm the data source and the LLM API are reachable.

Run:  python scripts/verify_setup.py

- Remotive API is public (no key) and should always pass if you have internet.
- The Claude check only runs if ANTHROPIC_API_KEY is set (in .env or the env).
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

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
    print("[2/2] Claude (Anthropic) API ...")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("      SKIP — ANTHROPIC_API_KEY not set. Add it to .env to test.")
        return True  # not a failure during setup week
    try:
        import anthropic

        client = anthropic.Anthropic()
        model = os.environ.get("JOB_SCOUT_MODEL", "claude-opus-4-8")
        resp = client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        print(f"      OK — {model} replied: {text.strip()!r}")
        return True
    except Exception as exc:  # noqa: BLE001
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
