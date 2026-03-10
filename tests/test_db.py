import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import pytest
from src.db.database import init_db, is_job_saved, save_job, _connect, DB_PATH

# --- Fixtures ---

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file for every test."""
    tmp_db = str(tmp_path / "test_jobs.db")
    monkeypatch.setattr("src.db.database.DB_PATH", tmp_db)
    init_db()
    yield tmp_db


def _sample_job(**overrides) -> dict:
    base = {
        "job_title": "Data Analyst",
        "company": "Acme Corp",
        "location": "Tel Aviv",
        "link": "https://www.linkedin.com/jobs/view/123/",
        "description": "A great job.",
        "source": "linkedin",
    }
    return {**base, **overrides}


# --- Schema ---

def test_table_exists():
    with _connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "jobs" in tables


def test_schema_has_source_column():
    with _connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert "source" in columns


def test_schema_has_scraped_at_column():
    with _connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert "scraped_at" in columns


# --- save_job ---

def test_save_job_persists_all_fields():
    job = _sample_job()
    save_job(job)
    with _connect() as conn:
        row = conn.execute("SELECT job_title, company, location, link, description, source FROM jobs").fetchone()
    assert row == ("Data Analyst", "Acme Corp", "Tel Aviv", "https://www.linkedin.com/jobs/view/123/", "A great job.", "linkedin")


def test_save_job_sets_scraped_at():
    save_job(_sample_job())
    with _connect() as conn:
        scraped_at = conn.execute("SELECT scraped_at FROM jobs").fetchone()[0]
    assert scraped_at is not None
    assert "T" in scraped_at  # ISO 8601 format


def test_save_job_duplicate_link_raises():
    save_job(_sample_job())
    with pytest.raises(sqlite3.IntegrityError):
        save_job(_sample_job())


def test_save_job_without_description():
    save_job(_sample_job(description=None))
    with _connect() as conn:
        desc = conn.execute("SELECT description FROM jobs").fetchone()[0]
    assert desc is None


# --- is_job_saved ---

def test_is_job_saved_returns_false_when_not_in_db():
    assert is_job_saved("https://www.linkedin.com/jobs/view/999/") is False


def test_is_job_saved_returns_true_after_save():
    job = _sample_job()
    save_job(job)
    assert is_job_saved(job["link"]) is True


def test_is_job_saved_does_not_match_partial_link():
    save_job(_sample_job(link="https://www.linkedin.com/jobs/view/123/"))
    assert is_job_saved("https://www.linkedin.com/jobs/view/12/") is False


# --- Migration ---

def test_migration_adds_source_to_existing_db(tmp_path, monkeypatch):
    """Simulate a DB created before source column existed."""
    tmp_db = str(tmp_path / "legacy.db")
    monkeypatch.setattr("src.db.database.DB_PATH", tmp_db)

    # Create table without source column (old schema)
    with sqlite3.connect(tmp_db) as conn:
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                description TEXT,
                scraped_at TEXT NOT NULL
            )
        """)

    # init_db should migrate it
    init_db()

    with sqlite3.connect(tmp_db) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert "source" in columns
