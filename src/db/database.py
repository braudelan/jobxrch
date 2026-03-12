# src/db/database.py
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "jobs.db")


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
                link        TEXT NOT NULL UNIQUE,
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
                assessment       TEXT NOT NULL,
                evaluated_at     TEXT NOT NULL
            )
        """)
        # Migration: add source column to existing DBs that predate it
        existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if "source" not in existing:
            conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown'")


def is_job_saved(link: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE link = ?", (link,)).fetchone()
        return row is not None


def get_job_id(link: str) -> int | None:
    with _connect() as conn:
        row = conn.execute("SELECT id FROM jobs WHERE link = ?", (link,)).fetchone()
        return row[0] if row else None


def save_evaluation(job_id: int, criteria_hash: str, assessment: str) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT INTO evaluations (job_id, criteria_hash, assessment, evaluated_at)
            VALUES (?, ?, ?, ?)
        """, (job_id, criteria_hash, assessment, datetime.now(timezone.utc).isoformat()))


def save_job(job: dict) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT INTO jobs (job_title, company, location, link, description, source, scraped_at)
            VALUES (:job_title, :company, :location, :link, :description, :source, :scraped_at)
        """, {**job, "scraped_at": datetime.now(timezone.utc).isoformat()})
