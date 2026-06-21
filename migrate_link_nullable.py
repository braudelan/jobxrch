"""
One-time migration: make the jobs.link column nullable (remove NOT NULL constraint).
Run once against data/jobs.db before starting the app.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print("No database found — nothing to migrate.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        # Check if migration is needed
        cols = {row[1]: row[3] for row in conn.execute("PRAGMA table_info(jobs)")}
        link_notnull = cols.get("link", 0)
        if not link_notnull:
            print("link column is already nullable — nothing to do.")
            return

        print("Migrating jobs.link to nullable…")
        conn.executescript("""
            PRAGMA foreign_keys = OFF;

            ALTER TABLE jobs RENAME TO jobs_old;

            CREATE TABLE jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title   TEXT NOT NULL,
                company     TEXT NOT NULL,
                location    TEXT NOT NULL,
                link        TEXT UNIQUE,
                description TEXT,
                source      TEXT NOT NULL,
                scraped_at  TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'saved',
                deleted     INTEGER NOT NULL DEFAULT 0
            );

            INSERT INTO jobs SELECT * FROM jobs_old;

            DROP TABLE jobs_old;

            PRAGMA foreign_keys = ON;
        """)
        print("Done.")


if __name__ == "__main__":
    migrate()
