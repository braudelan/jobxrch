# eval/db.py
"""DB access layer for the llmEV eval pipeline.

Reads from raw_llm_log and writes to cv_tailor_scores. Uses the same
data/jobs.db as the main app — scored records join naturally to
raw_llm_log and jobs.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jobs.db")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_scores_table() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cv_tailor_scores (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id           INTEGER NOT NULL REFERENCES raw_llm_log(id),
                job_id           INTEGER REFERENCES jobs(id),
                timestamp        TEXT NOT NULL,
                model            TEXT NOT NULL,
                context          TEXT NOT NULL,
                bullet_title     TEXT NOT NULL,
                bullet_text      TEXT NOT NULL,
                source_sections  TEXT NOT NULL,
                missing_sections TEXT NOT NULL,
                reference        TEXT,
                grounding_score  REAL,
                grounding_label  TEXT NOT NULL,
                relevance_score  REAL,
                relevance_label  TEXT,
                scored_at        TEXT NOT NULL
            )
        """)


def get_cv_tailor_log_entries() -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM raw_llm_log WHERE task_type = 'cv_tailor' ORDER BY timestamp ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_scored_log_ids() -> set[int]:
    """Return log_ids that already have scores so the runner can skip them."""
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT log_id FROM cv_tailor_scores").fetchall()
        return {r[0] for r in rows}


def save_score_records(records: list[dict]) -> None:
    scored_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for r in records:
            conn.execute(
                """
                INSERT INTO cv_tailor_scores (
                    log_id, job_id, timestamp, model, context,
                    bullet_title, bullet_text, source_sections, missing_sections,
                    reference, grounding_score, grounding_label,
                    relevance_score, relevance_label, scored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["log_id"],
                    r.get("job_id"),
                    r["timestamp"],
                    r["model"],
                    r["context"],
                    r["bullet_title"],
                    r["bullet_text"],
                    json.dumps(r["source_sections"]),
                    json.dumps(r["missing_sections"]),
                    r.get("reference"),
                    r.get("grounding_score"),
                    r["grounding_label"],
                    r.get("relevance_score"),
                    r.get("relevance_label"),
                    scored_at,
                ),
            )
