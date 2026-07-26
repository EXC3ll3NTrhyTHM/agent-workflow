"""Stable integer ids for postings whose source doesn't provide one.

Alert dedup lives in SQLite keyed by job id, so ids must be identical across
runs. Python's built-in ``hash()`` is salted per process (PYTHONHASHSEED) —
using it would make every posting look "new" on every run and re-alert
endlessly. This digest-based id is deterministic forever.
"""

from __future__ import annotations

import hashlib


def stable_id(text: str) -> int:
    """Map a unique posting string (URL/guid/slug) to a stable positive int."""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)  # 48 bits — plenty for a few thousand postings
