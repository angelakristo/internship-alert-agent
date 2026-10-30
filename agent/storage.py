"""SQLite storage for remembering job postings that have already been seen."""

# sqlite3 е вграден во Python – не треба ништо да се инсталира.
import sqlite3

# closing гарантира дека врската со базата ќе се затвори на крајот.
from contextlib import closing

# datetime ни треба за да го запишеме кога првпат сме го виделе огласот.
from datetime import datetime, timezone

# Path ни овозможува лесно да работиме со патеки до фајлови и папки.
from pathlib import Path

from agent.models import Job

# Главната папка на проектот. __file__ е овој фајл (agent/storage.py),
# .parent е папката agent/, а уште еден .parent е главната папка на проектот.
# resolve() ја прави патеката апсолутна.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Стандардна патека до базата, ако не се зададе друга: <проект>/data/jobs.db.
# Секогаш е иста, без разлика од која папка е стартуван програмот.
DEFAULT_DB_PATH = str(PROJECT_ROOT / "data" / "jobs.db")


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Ја креира табелата seen_jobs ако сè уште не постои."""
    # sqlite3.connect го отвора фајлот (или го креира ако не постои).
    with closing(sqlite3.connect(db_path)) as conn:
        # "with conn" автоматски ги зачувува промените (commit) на крајот.
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
    """Ги враќа само огласите што ги немаме видено досега."""
    # Се осигуруваме дека табелата постои, за да не добиеме грешка.
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        # Ги читаме сите job_id што се веќе зачувани и ги ставаме во set
        # (set овозможува многу брза проверка „дали е внатре“).
        rows = conn.execute("SELECT job_id FROM seen_jobs").fetchall()
        seen_ids = {row[0] for row in rows}

    # Ги задржуваме само огласите чиј job_id не е во базата.
    return [job for job in jobs if job.job_id not in seen_ids]


def mark_as_seen(jobs: list[Job], db_path: str = DEFAULT_DB_PATH) -> None:
    """Ги зачувува огласите во базата за следниот пат да не се сметаат за нови."""
    init_db(db_path)

    # Моменталното време во UTC, во стандарден формат (на пр. 2026-10-30T18:00:00+00:00).
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            for job in jobs:
                # "INSERT OR IGNORE" ако огласот веќе постои, не прави ништо,
                # па first_seen останува датумот кога првпат го видовме.
                # Знаците ? се место за вредностите – ова е безбедниот начин
                # да се стават податоци во SQL.
                conn.execute(
                    """
                    INSERT OR IGNORE INTO seen_jobs
                        (job_id, company, title, location, url, first_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (job.job_id, job.company, job.title, job.location, job.url, now),
                )


# Мал тест: python -m agent.storage
if __name__ == "__main__":
    import os

    # Користиме посебна тест база за да не ја допреме вистинската.
    test_db = "data/test_jobs.db"

    # Два пример огласи.
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
        # Првпат: базата е празна, па двата огласи се нови.
        new_jobs = filter_new_jobs(example_jobs, test_db)
        print(f"Нови огласи пред зачувување: {len(new_jobs)} (очекувано 2)")

        # Ги означуваме како видени.
        mark_as_seen(new_jobs, test_db)

        # Вторпат: веќе се во базата, па нема нови.
        new_jobs = filter_new_jobs(example_jobs, test_db)
        print(f"Нови огласи после зачувување: {len(new_jobs)} (очекувано 0)")
    finally:
        # На крај ја бришеме тест базата (finally се извршува дури и ако има грешка).
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"Тест базата {test_db} е избришана.")
