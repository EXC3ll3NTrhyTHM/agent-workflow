"""SQLite persistence: ranked listings, alerted jobs, and tried queries.

State must survive between daily runs so the agent can (a) avoid repeating
search queries and (b) avoid re-alerting on the same job.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY,        -- source job id (or stable digest, see ids.py)
    title        TEXT NOT NULL,
    company      TEXT NOT NULL,
    url          TEXT NOT NULL,
    score        REAL NOT NULL,              -- 0-10 match score
    reasoning    TEXT,                       -- why the LLM gave this score
    alerted      INTEGER NOT NULL DEFAULT 0, -- 1 once an email has been sent
    first_seen   TEXT NOT NULL DEFAULT (datetime('now')),
    last_scored  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tried_queries (
    query     TEXT PRIMARY KEY,
    tried_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,               -- e.g. 'last_digest_at'
    value  TEXT NOT NULL
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive column migrations — executescript can't alter existing tables."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "pitch" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN pitch TEXT")


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open (creating/migrating if needed) the DB; commits on clean exit."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_job(
    conn: sqlite3.Connection,
    *,
    job_id: int,
    title: str,
    company: str,
    url: str,
    score: float,
    reasoning: str,
) -> None:
    conn.execute(
        """
        INSERT INTO jobs (id, title, company, url, score, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            score = excluded.score,
            reasoning = excluded.reasoning,
            last_scored = datetime('now')
        """,
        (job_id, title, company, url, score, reasoning),
    )


def mark_alerted(conn: sqlite3.Connection, job_id: int) -> None:
    conn.execute("UPDATE jobs SET alerted = 1 WHERE id = ?", (job_id,))


def has_been_alerted(conn: sqlite3.Connection, job_id: int) -> bool:
    row = conn.execute("SELECT alerted FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return bool(row and row["alerted"])


def record_query(conn: sqlite3.Connection, query: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO tried_queries (query) VALUES (?)", (query.strip().lower(),)
    )


def query_already_tried(conn: sqlite3.Connection, query: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM tried_queries WHERE query = ?", (query.strip().lower(),)
    ).fetchone()
    return row is not None


def ranked_listings(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM jobs ORDER BY score DESC, last_scored DESC LIMIT ?", (limit,)
    ).fetchall()


def set_pitch(conn: sqlite3.Connection, job_id: int, pitch: str) -> None:
    conn.execute("UPDATE jobs SET pitch = ? WHERE id = ?", (pitch, job_id))


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def utcnow(conn: sqlite3.Connection) -> str:
    """SQLite's clock, so meta timestamps compare cleanly with first_seen."""
    return conn.execute("SELECT datetime('now') AS now").fetchone()["now"]


def jobs_for_digest(
    conn: sqlite3.Connection, *, since: str | None, floor: float
) -> list[sqlite3.Row]:
    """Jobs at/above `floor` first seen after `since` (all history if None)."""
    if since is None:
        return conn.execute(
            "SELECT * FROM jobs WHERE score >= ? ORDER BY score DESC", (floor,)
        ).fetchall()
    return conn.execute(
        "SELECT * FROM jobs WHERE score >= ? AND first_seen > ? ORDER BY score DESC",
        (floor, since),
    ).fetchall()
