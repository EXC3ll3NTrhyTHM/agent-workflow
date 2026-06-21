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
    id           INTEGER PRIMARY KEY,        -- Remotive job id
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
"""


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
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
