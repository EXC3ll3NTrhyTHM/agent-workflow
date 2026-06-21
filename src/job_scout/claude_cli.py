"""Talk to Claude by shelling out to the `claude` CLI — no auth code, no SDK.

This mirrors how the existing tmobile-scout app authenticates: the `claude`
binary manages its own credentials. On a personal machine those live in
``~/.claude/.credentials.json`` (an OAuth token from `claude login`, refreshed
automatically). If ``ANTHROPIC_API_KEY`` is set in the environment, the CLI uses
that instead. This process never sees, stores, or transmits the credential — it
only needs to (a) run the same binary and (b) run as a user that can read that
credentials file (or have the key in its env).

Deployment notes (the parts that actually bite):
- cron/systemd run with a minimal PATH, so configure an ABSOLUTE path to the
  binary via ``CLAUDE_PATH`` (find it with ``which claude``). A bare ``claude``
  will fail with "command not found" outside an interactive shell.
- If the service runs as a different OS user, set ``CLAUDE_HOME`` so the CLI
  finds the right ``~/.claude`` — or provide ``ANTHROPIC_API_KEY`` instead.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# Human-text markers the CLI prints when quota / rate limits are hit.
_RATE_LIMIT_MARKERS = ("out of extra usage", "rate limit", "resets ")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class ClaudeError(RuntimeError):
    """Base error for CLI invocation problems (binary missing, timeout, etc.)."""


class ClaudeAuthError(ClaudeError):
    """The CLI couldn't authenticate (not logged in / expired, or bad key)."""


class ClaudeRateLimitError(ClaudeError):
    """The CLI reported a rate limit or exhausted quota."""


def resolve_claude_path(configured: str | None = None) -> str:
    """Return a path to the `claude` binary (configured value wins)."""
    if configured:
        return configured
    found = shutil.which("claude")
    if found:
        return found
    raise ClaudeError(
        "`claude` binary not found. Install Claude Code and set CLAUDE_PATH to "
        "its absolute path (find it with `which claude`)."
    )


def has_credentials(home: str | None = None) -> bool:
    """True if a usable credential exists: a CLI login file or an API key."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    base = Path(home or os.environ.get("HOME", str(Path.home())))
    return (base / ".claude" / ".credentials.json").exists()


def run_claude(
    prompt: str,
    *,
    claude_path: str | None = None,
    home: str | None = None,
    model: str | None = None,
    timeout: int = 180,
) -> str:
    """Run ``claude -p <prompt>`` and return stdout.

    Raises :class:`ClaudeRateLimitError` if the CLI reports a limit, and
    :class:`ClaudeAuthError` / :class:`ClaudeError` on other failures.
    """
    path = resolve_claude_path(claude_path)
    cmd = [path, "-p", prompt]
    if model:
        cmd += ["--model", model]

    env = dict(os.environ)
    if home:
        env["HOME"] = home

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
        )
    except FileNotFoundError as exc:
        raise ClaudeError(f"claude binary not found at {path!r} — fix CLAUDE_PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeError(f"claude timed out after {timeout}s.") from exc

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    haystack = f"{out}\n{err}".lower()

    # Check limits first — the CLI may print these as plain text and still exit 0.
    if any(marker in haystack for marker in _RATE_LIMIT_MARKERS):
        raise ClaudeRateLimitError(out or err or "rate limited / out of quota")
    if result.returncode != 0:
        raise ClaudeAuthError(
            err
            or out
            or f"claude exited {result.returncode}. "
            "If this host has never run `claude login`, do that once."
        )
    return out


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of CLI stdout (which may include prose)."""
    match = _JSON_RE.search(text)
    if not match:
        raise ClaudeError(f"No JSON object found in Claude output: {text[:200]!r}")
    return json.loads(match.group(0))
