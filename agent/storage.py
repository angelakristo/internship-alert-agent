"""SQLite storage for remembering job postings that have already been seen."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from agent.models import Job

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = str(PROJECT_ROOT / "data" / "jobs.db")


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    job_id     TEXT PRIMARY KEY,
                    company    TEXT,
                    title      TEXT,
                    location   TEXT,
                    url        TEXT,
                    first_seen TEXT
                )
                """
            )


def filter_new_jobs(jobs: list[Job], db_path: str = DEFAULT_DB_PATH) -> list[Job]:
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT job_id FROM seen_jobs").fetchall()
        seen_ids = {row[0] for row in rows}

    return [job for job in jobs if job.job_id not in seen_ids]


def mark_as_seen(jobs: list[Job], db_path: str = DEFAULT_DB_PATH) -> None:
    init_db(db_path)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            for job in jobs:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO seen_jobs
                        (job_id, company, title, location, url, first_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (job.job_id, job.company, job.title, job.location, job.url, now),
                )


if __name__ == "__main__":
    import os

    test_db = "data/test_jobs.db"

    example_jobs = [
        Job(
            company="Example Corp",
            title="Software Engineering Intern",
            location="MK",
            url="https://example.com/careers/1",
            source="manual",
        ),
        Job(
            company="Example Corp",
            title="Data Science Intern",
            location="MK",
            url="https://example.com/careers/2",
            source="manual",
        ),
    ]

    try:
        new_jobs = filter_new_jobs(example_jobs, test_db)
        print(f"Нови огласи пред зачувување: {len(new_jobs)} (очекувано 2)")

        mark_as_seen(new_jobs, test_db)

        new_jobs = filter_new_jobs(example_jobs, test_db)
        print(f"Нови огласи после зачувување: {len(new_jobs)} (очекувано 0)")
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"Тест базата {test_db} е избришана.")
