"""Entry point for the Internship Alert Agent, run on GitHub Actions every 6 hours."""

import argparse
import logging
import os
import sys
from functools import partial
from pathlib import Path

import yaml

from agent.filters import filter_relevant
from agent.notifier import send_job_alert
from agent.scrapers import (
    ashby,
    codechem,
    greenhouse,
    joberty,
    jsonld,
    netcetera,
    rldatix,
    smartrecruiters,
    sorsix,
    talentlyft,
    teamtailor,
    vrabotuvanje,
    wordpress,
)
from agent.storage import DEFAULT_DB_PATH, filter_new_jobs, mark_as_seen

SCRAPERS = [
    netcetera.scrape,
    vrabotuvanje.scrape,
    joberty.scrape,
    codechem.scrape,
    rldatix.scrape,
    sorsix.scrape,
]

COMPANIES_FILE = Path(__file__).resolve().parent / "config" / "companies.yaml"

ATS_SCRAPERS = {
    "greenhouse": (greenhouse.scrape, ["board_token"]),
    "smartrecruiters": (smartrecruiters.scrape, ["company_id"]),
    "ashby": (ashby.scrape, ["job_board_name"]),
    "teamtailor": (teamtailor.scrape, ["career_domain"]),
    "talentlyft": (talentlyft.scrape, ["career_domain"]),
    "wordpress": (wordpress.scrape, ["domain", "post_type"]),
    "jsonld": (jsonld.scrape, ["careers_url"]),
}

logger = logging.getLogger("agent")


def load_ats_tasks():
    with open(COMPANIES_FILE, encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    tasks = []
    invalid = []
    for company in config.get("companies") or []:
        name = company.get("name", "(no name)")
        company_type = company.get("type")

        if company_type not in ATS_SCRAPERS:
            logger.error("companies.yaml: unknown type \"%s\" for %s.", company_type, name)
            invalid.append(f"{company_type}: {name}")
            continue

        scraper, param_names = ATS_SCRAPERS[company_type]

        missing = [param for param in param_names if not company.get(param)]
        if missing:
            logger.error("companies.yaml: %s is missing \"%s\".", name, ", ".join(missing))
            invalid.append(f"{company_type}: {name}")
            continue

        params = [company[param] for param in param_names]
        task = partial(scraper, name, *params)
        tasks.append((f"{company_type}: {name}", task))
    return tasks, invalid


def run_scrapers():
    all_jobs = []
    failed_scrapers = []

    tasks = [(scraper.__module__, scraper) for scraper in SCRAPERS]

    try:
        ats_tasks, invalid = load_ats_tasks()
        tasks.extend(ats_tasks)
        failed_scrapers.extend(invalid)
    except Exception:
        logger.exception("config/companies.yaml could not be read")
        failed_scrapers.append("config/companies.yaml")

    for name, scraper in tasks:
        try:
            jobs = scraper()
            logger.info("%s: found %d jobs", name, len(jobs))
            all_jobs.extend(jobs)
        except Exception:
            logger.exception("%s: scraper failed", name)
            failed_scrapers.append(name)
    return all_jobs, failed_scrapers


def main() -> int:
    parser = argparse.ArgumentParser(description="Internship Alert Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run all steps, but do NOT send email and do NOT write to the database",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.dry_run:
        logger.info("DRY RUN: no email will be sent and nothing will be written to the database.")

    all_jobs, failed_scrapers = run_scrapers()

    relevant = filter_relevant(all_jobs)

    if args.dry_run and not os.path.exists(DEFAULT_DB_PATH):
        new_jobs = relevant
    else:
        new_jobs = filter_new_jobs(relevant)

    email_sent = False
    email_failed = False
    if new_jobs and args.dry_run:
        logger.info("DRY RUN: would send an email with %d jobs:", len(new_jobs))
        for job in new_jobs:
            logger.info("  - %s | %s | %s | %s", job.company, job.title, job.location, job.url)
    elif new_jobs:
        try:
            send_job_alert(new_jobs)
            email_sent = True
            mark_as_seen(new_jobs)
        except Exception:
            email_failed = True
            logger.exception("Sending the email failed. The jobs were NOT marked as seen.")

    logger.info(
        "Summary: %d jobs total, %d relevant, %d new, email sent: %s",
        len(all_jobs),
        len(relevant),
        len(new_jobs),
        "yes" if email_sent else "no",
    )
    if failed_scrapers:
        logger.error("Failed scrapers: %s", ", ".join(failed_scrapers))
    else:
        logger.info("Failed scrapers: none")

    return 1 if email_failed or failed_scrapers else 0


if __name__ == "__main__":
    sys.exit(main())
