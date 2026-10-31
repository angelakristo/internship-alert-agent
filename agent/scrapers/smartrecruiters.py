"""Generic scraper for companies that use the SmartRecruiters ATS (public Postings API)."""

import json
import logging
import time
from urllib.parse import quote

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

API_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings?limit={limit}&offset={offset}"

JOB_PAGE_URL = "https://jobs.smartrecruiters.com/{company}/{job_id}"

PAGE_SIZE = 100

MAX_PAGES = 10

PAUSE_SECONDS = 2


def _location(item: dict) -> str:
    location = item.get("location") or {}
    text = location.get("fullLocation") or ", ".join(
        part for part in [location.get("city"), location.get("country")] if part
    )
    if location.get("remote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _description(item: dict) -> str:
    parts = []
    for field, label in [("department", "Department"), ("function", "Function"), ("experienceLevel", "Level")]:
        value = (item.get(field) or {}).get("label")
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def scrape(company_name: str, company_id: str) -> list[Job]:
    jobs = []

    for page in range(MAX_PAGES):
        if page > 0:
            time.sleep(PAUSE_SECONDS)

        url = API_URL.format(company_id=quote(company_id), limit=PAGE_SIZE, offset=page * PAGE_SIZE)
        data = json.loads(fetch_html(url))

        for item in data["content"]:
            company_slug = (item.get("company") or {}).get("identifier") or company_id
            jobs.append(
                Job(
                    company=company_name,
                    title=item["name"],
                    location=_location(item),
                    url=JOB_PAGE_URL.format(company=quote(company_slug), job_id=item["id"]),
                    source="smartrecruiters",
                    description=_description(item),
                )
            )

        if not data["content"] or len(jobs) >= data["totalFound"]:
            break
    else:
        logger.warning(
            "smartrecruiters (%s): read the maximum of %d pages, there may be more jobs.",
            company_name,
            MAX_PAGES,
        )

    if not jobs:
        logger.warning(
            "smartrecruiters (%s): found 0 jobs. Check the company_id \"%s\".",
            company_name,
            company_id,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("Endava", "Endava")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Total jobs: {len(found_jobs)}")
