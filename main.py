"""Entry point for the Internship Alert Agent, run on GitHub Actions every 6 hours."""

# argparse ги чита опциите од командната линија (на пр. --dry-run).
import argparse

# logging служи за печатење пораки со време и ниво (INFO, WARNING, ERROR).
import logging

# os.path.exists проверува дали фајлот постои.
import os

# sys.exit го завршува програмот со код (0 = успех, 1 = грешка).
import sys

# partial „подготвува“ функција со веќе зададени аргументи, за да ја повикаме подоцна.
from functools import partial

# Path ни помага да ја најдеме патеката до config/companies.yaml.
from pathlib import Path

# yaml го чита config/companies.yaml.
import yaml

from agent.filters import filter_relevant
from agent.notifier import send_job_alert
from agent.scrapers import (
    ashby,
    greenhouse,
    joberty,
    netcetera,
    smartrecruiters,
    teamtailor,
    vrabotuvanje,
)
from agent.storage import DEFAULT_DB_PATH, filter_new_jobs, mark_as_seen

# Сите scrapers што агентот ги извршува. За нова компанија, додај ја нејзината
# scrape функција тука.
SCRAPERS = [
    netcetera.scrape,
    vrabotuvanje.scrape,
    joberty.scrape,
]

# Компаниите што користат систем за огласи (ATS) се во овој фајл.
# Патеката е во однос на main.py, па не зависи од папката од која стартуваме.
COMPANIES_FILE = Path(__file__).resolve().parent / "config" / "companies.yaml"

# За секој type од companies.yaml: која scrape функција го чита
# и кој параметар од yaml-от ѝ треба (покрај името на компанијата).
# За нов ATS систем, додај ред тука.
ATS_SCRAPERS = {
    "greenhouse": (greenhouse.scrape, "board_token"),
    "smartrecruiters": (smartrecruiters.scrape, "company_id"),
    "ashby": (ashby.scrape, "job_board_name"),
    "teamtailor": (teamtailor.scrape, "career_domain"),
}

logger = logging.getLogger("agent")


def load_ats_tasks():
    """Ги чита компаниите од companies.yaml и за секоја подготвува scraper.

    Враќа два резултати:
    - листа од парови (име, функција), на пр. ("greenhouse: Loka", ...)
    - листа со имиња на компании што се погрешно запишани во yaml-от
    """
    with open(COMPANIES_FILE, encoding="utf-8") as file:
        # safe_load го чита YAML-от безбедно. "or {}" е за празен фајл.
        config = yaml.safe_load(file) or {}

    tasks = []
    invalid = []
    for company in config.get("companies") or []:
        name = company.get("name", "(без име)")
        company_type = company.get("type")

        # Непознат type: логираме грешка и продолжуваме со другите компании.
        if company_type not in ATS_SCRAPERS:
            logger.error("companies.yaml: непознат type „%s“ за %s.", company_type, name)
            invalid.append(f"{company_type}: {name}")
            continue

        scraper, param_name = ATS_SCRAPERS[company_type]

        # Недостасува параметарот (на пр. board_token): исто така грешка.
        if not company.get(param_name):
            logger.error("companies.yaml: %s нема „%s“.", name, param_name)
            invalid.append(f"{company_type}: {name}")
            continue

        # partial ги „заклучува“ аргументите, па подоцна ја повикуваме само со ().
        task = partial(scraper, name, company[param_name])
        tasks.append((f"{company_type}: {name}", task))
    return tasks, invalid


def run_scrapers():
    """Ги извршува сите scrapers.

    Враќа два резултати: сите пронајдени огласи заедно и листа со имињата
    на scrapers што паднале.
    """
    all_jobs = []
    failed_scrapers = []

    # Листа од парови (име, функција). Името на постојните scrapers е името
    # на модулот, на пр. "agent.scrapers.netcetera", за полесно да знаеме кој паднал.
    tasks = [(scraper.__module__, scraper) for scraper in SCRAPERS]

    # Ги додаваме ATS компаниите од companies.yaml. Ако фајлот не може да се
    # прочита, тоа го бележиме како пад, но постојните scrapers сепак работат.
    # Погрешно запишаните компании ги бележиме како паднати, за да се видат во резимето.
    try:
        ats_tasks, invalid = load_ats_tasks()
        tasks.extend(ats_tasks)
        failed_scrapers.extend(invalid)
    except Exception:
        logger.exception("config/companies.yaml не може да се прочита")
        failed_scrapers.append("config/companies.yaml")

    for name, scraper in tasks:
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
