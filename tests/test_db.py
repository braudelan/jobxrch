import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import pytest
from src.db.database import (
    init_db, is_job_saved, save_job, _connect, DB_PATH,
    get_profile, save_profile, get_profile_updated_at,
    save_message, get_messages, get_messages_since,
)

# --- Fixtures ---

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file for every test. Block criteria seeding."""
    tmp_db = str(tmp_path / "test_jobs.db")
    monkeypatch.setattr("src.db.database.DB_PATH", tmp_db)
    monkeypatch.setattr("src.db.database.CRITERIA_PATH", str(tmp_path / "nonexistent_criteria.txt"))
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

# --- profile ---

def test_get_profile_empty():
    assert get_profile() == ""


def test_save_and_get_profile_roundtrip():
    save_profile("I am a senior engineer.")
    assert get_profile() == "I am a senior engineer."


def test_save_profile_twice_upserts():
    save_profile("first")
    save_profile("second")
    assert get_profile() == "second"
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM user_profile").fetchone()[0]
    assert count == 1


def test_get_profile_updated_at_returns_iso_after_save():
    save_profile("something")
    updated_at = get_profile_updated_at()
    assert updated_at is not None
    assert "T" in updated_at


# --- messages ---

def test_save_and_get_messages_roundtrip():
    save_message("user", "hello")
    save_message("assistant", "hi there")
    msgs = get_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "hi there"


def test_get_messages_limit():
    for i in range(5):
        save_message("user", f"msg {i}")
    msgs = get_messages(limit=2)
    assert len(msgs) == 2


def test_get_messages_since():
    save_message("user", "first")
    first_id = get_messages()[-1]["id"]
    save_message("user", "second")
    save_message("assistant", "third")
    later = get_messages_since(first_id)
    assert len(later) == 2
    assert later[0]["content"] == "second"
    assert later[1]["content"] == "third"


# --- init_db seeds from criteria file ---

def test_init_db_seeds_profile_from_criteria(tmp_path, monkeypatch):
    tmp_db = str(tmp_path / "seed.db")
    criteria_file = tmp_path / "criteria.txt"
    criteria_file.write_text("Looking for remote data roles.")
    monkeypatch.setattr("src.db.database.DB_PATH", tmp_db)
    monkeypatch.setattr("src.db.database.CRITERIA_PATH", str(criteria_file))
    init_db()
    assert get_profile() == "Looking for remote data roles."


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
