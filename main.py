"""Entry point for the Internship Alert Agent, run on GitHub Actions every 6 hours."""

# argparse ги чита опциите од командната линија (на пр. --dry-run).
import argparse

# logging служи за печатење пораки со време и ниво (INFO, WARNING, ERROR).
import logging

# os.path.exists проверува дали фајлот постои.
import os

# sys.exit го завршува програмот со код (0 = успех, 1 = грешка).
import sys

from agent.filters import filter_relevant
from agent.notifier import send_job_alert
from agent.scrapers import joberty, netcetera, vrabotuvanje
from agent.storage import DEFAULT_DB_PATH, filter_new_jobs, mark_as_seen

# Сите scrapers што агентот ги извршува. За нова компанија, додај ја нејзината
# scrape функција тука.
SCRAPERS = [
    netcetera.scrape,
    vrabotuvanje.scrape,
    joberty.scrape,
]

logger = logging.getLogger("agent")


def run_scrapers():
    """Ги извршува сите scrapers.

    Враќа два резултати: сите пронајдени огласи заедно и листа со имињата
    на scrapers што паднале.
    """
    all_jobs = []
    failed_scrapers = []
    for scraper in SCRAPERS:
        # Името на модулот, на пр. "agent.scrapers.netcetera", за полесно да знаеме кој паднал.
        name = scraper.__module__
        # Секој scraper е во посебен try/except: ако еден падне, другите продолжуваат.
        try:
            jobs = scraper()
            logger.info("%s: пронајдени %d огласи", name, len(jobs))
            all_jobs.extend(jobs)
        except Exception:
            # logger.exception ја печати и целата грешка (traceback).
            logger.exception("%s: scraper-от падна", name)
            # Го паметиме името за да го прикажеме во резимето.
            failed_scrapers.append(name)
    return all_jobs, failed_scrapers


def main() -> int:
    """Главниот тек на агентот.

    Враќа 0 ако сè е во ред, 1 ако email-от не успеал или ако некој scraper паднал.
    """
    # Ја дефинираме опцијата --dry-run.
    parser = argparse.ArgumentParser(description="Internship Alert Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="изврши ги сите чекори, но НЕ праќај email и НЕ запишувај во базата",
    )
    args = parser.parse_args()

    # Формат на пораките: време, ниво, порака.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.dry_run:
        logger.info("DRY RUN: нема да се прати email и нема да се запише во базата.")

    # 1. Ги собираме огласите од сите компании.
    all_jobs, failed_scrapers = run_scrapers()

    # 2. Ги задржуваме само релевантните (пракса, IT, добра локација).
    relevant = filter_relevant(all_jobs)

    # 3. Од релевантните ги задржуваме само оние што не сме ги виделе досега.
    if args.dry_run and not os.path.exists(DEFAULT_DB_PATH):
        # Во dry-run не сакаме да ја креираме базата, а ако ја нема,
        # тогаш сите релевантни огласи се нови.
        new_jobs = relevant
    else:
        new_jobs = filter_new_jobs(relevant)

    # 4. Праќаме email и ги означуваме огласите како видени.
    email_sent = False
    email_failed = False
    if new_jobs and args.dry_run:
        # Само печатиме што би испратиле.
        logger.info("DRY RUN: би се испратил email со %d огласи:", len(new_jobs))
        for job in new_jobs:
            logger.info("  - %s | %s | %s | %s", job.company, job.title, job.location, job.url)
    elif new_jobs:
        try:
            send_job_alert(new_jobs)
            email_sent = True
            # ДУРИ откако email-от е успешно испратен, ги означуваме како видени.
            # Ако email-от падне, следниот пат ќе пробаме повторно.
            mark_as_seen(new_jobs)
        except Exception:
            email_failed = True
            logger.exception("Испраќањето email не успеа. Огласите НЕ се означени како видени.")

    # 5. Резиме.
    logger.info(
        "Резиме: вкупно %d огласи, %d релевантни, %d нови, email испратен: %s",
        len(all_jobs),
        len(relevant),
        len(new_jobs),
        "да" if email_sent else "не",
    )
    if failed_scrapers:
        logger.error("Паднати scrapers: %s", ", ".join(failed_scrapers))
    else:
        logger.info("Паднати scrapers: нема")

    # Ако email-от или некој scraper паднал, враќаме 1 за GitHub Actions
    # да го означи извршувањето како неуспешно.
    return 1 if email_failed or failed_scrapers else 0


if __name__ == "__main__":
    sys.exit(main())
