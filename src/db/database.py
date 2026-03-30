# src/db/database.py
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "jobs.db")
CRITERIA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "criteria.txt")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title   TEXT NOT NULL,
                company     TEXT NOT NULL,
                location    TEXT NOT NULL,
                link        TEXT UNIQUE,
                description TEXT,
                source      TEXT NOT NULL,
                scraped_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id           INTEGER NOT NULL REFERENCES jobs(id),
                criteria_hash    TEXT NOT NULL,
                score            INTEGER NOT NULL DEFAULT 0,
                summary          TEXT NOT NULL DEFAULT '',
                assessment       TEXT NOT NULL,
                evaluated_at     TEXT NOT NULL
            )
        """)
        # Migrations for evaluations table
        eval_cols = {row[1] for row in conn.execute("PRAGMA table_info(evaluations)")}
        if "score" not in eval_cols:
            conn.execute(
                "ALTER TABLE evaluations ADD COLUMN score INTEGER NOT NULL DEFAULT 0"
            )
        if "summary" not in eval_cols:
            conn.execute(
                "ALTER TABLE evaluations ADD COLUMN summary TEXT NOT NULL DEFAULT ''"
            )
        # Migrations for jobs table
        job_cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if "status" not in job_cols:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'saved'"
            )
        if "deleted" not in job_cols:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0"
            )
        # Migration: add source column to existing DBs that predate it
        existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if "source" not in existing:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown'"
            )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id         INTEGER PRIMARY KEY,
                content    TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
        """)
        # Seed profile from criteria.txt on first startup
        row = conn.execute("SELECT id FROM user_profile WHERE id = 1").fetchone()
        if row is None and os.path.exists(CRITERIA_PATH):
            with open(CRITERIA_PATH) as f:
                seed = f.read().strip()
            conn.execute(
                "INSERT INTO user_profile (id, content, updated_at) VALUES (1, ?, ?)",
                (seed, datetime.now(timezone.utc).isoformat()),
            )


def is_job_saved(link: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE link = ?", (link,)).fetchone()
        return row is not None


def get_job_id(link: str) -> Optional[int]:
    with _connect() as conn:
        row = conn.execute("SELECT id FROM jobs WHERE link = ?", (link,)).fetchone()
        return row[0] if row else None


def save_evaluation(job_id: int, criteria_hash: str, result) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO evaluations (job_id, criteria_hash, score, summary, assessment, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                job_id,
                criteria_hash,
                result.score,
                result.summary,
                result.assessment,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_job_by_link(link: str) -> Optional[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE link = ?", (link,)).fetchone()
        return dict(row) if row else None


def get_all_jobs() -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT j.id, j.job_title, j.company, j.location, j.link, j.description,
                   j.source, j.status, j.scraped_at,
                   e.score, e.summary, e.assessment, e.evaluated_at
            FROM jobs j
            LEFT JOIN (
                SELECT job_id, score, summary, assessment, evaluated_at
                FROM evaluations
                WHERE id IN (SELECT MAX(id) FROM evaluations GROUP BY job_id)
            ) e ON j.id = e.job_id
            WHERE j.deleted = 0
            ORDER BY e.score DESC NULLS LAST, j.scraped_at DESC
        """).fetchall()
        return [dict(row) for row in rows]


def update_job_status(job_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))


def get_unevaluated_jobs() -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT j.*
            FROM jobs j
            LEFT JOIN (
                SELECT job_id FROM evaluations
                WHERE id IN (SELECT MAX(id) FROM evaluations GROUP BY job_id)
            ) e ON j.id = e.job_id
            WHERE j.deleted = 0 AND e.job_id IS NULL
            ORDER BY j.scraped_at DESC
        """).fetchall()
        return [dict(row) for row in rows]


def get_job(job_id: int) -> Optional[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT j.*, e.score, e.summary, e.assessment, e.criteria_hash, e.evaluated_at
            FROM jobs j
            LEFT JOIN (
                SELECT * FROM evaluations
                WHERE id IN (SELECT MAX(id) FROM evaluations GROUP BY job_id)
            ) e ON j.id = e.job_id
            WHERE j.id = ?
        """,
            (job_id,),
        ).fetchone()
        return dict(row) if row else None


def update_job_metadata(
    job_id: int, job_title: str, company: str, location: str
) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET job_title = ?, company = ?, location = ? WHERE id = ?",
            (job_title, company, location, job_id),
        )


def delete_job(job_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET deleted = 1 WHERE id = ?", (job_id,))


def save_job_manual(
    job_title: str,
    company: str,
    location: str,
    link: Optional[str],
    description: str,
) -> int:
    """Save a job that the user has manually inputted, rather than scraped from the web. Returns the new job ID."""
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (job_title, company, location, link, description, source, scraped_at)
            VALUES (?, ?, ?, ?, ?, 'manual', ?)
        """,
            (
                job_title,
                company,
                location,
                link or None,
                description,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid


def save_job(job: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_title, company, location, link, description, source, scraped_at)
            VALUES (:job_title, :company, :location, :link, :description, :source, :scraped_at)
        """,
            {**job, "scraped_at": datetime.now(timezone.utc).isoformat()},
        )


def get_profile() -> str:
    with _connect() as conn:
        row = conn.execute("SELECT content FROM user_profile WHERE id = 1").fetchone()
        return row[0] if row else ""


def save_profile(content: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_profile (id, content, updated_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
        """,
            (content, datetime.now(timezone.utc).isoformat()),
        )


def get_profile_updated_at() -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT updated_at FROM user_profile WHERE id = 1"
        ).fetchone()
        return row[0] if row else None


def save_message(role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, datetime.now(timezone.utc).isoformat()),
        )


def get_messages(limit: int = 200) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM chat_messages ORDER BY created_at ASC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_messages_since(since_id: int) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE id > ? ORDER BY created_at ASC",
            (since_id,),
        ).fetchall()
        return [dict(r) for r in rows]
