"""Generic scraper for companies that use the Ashby ATS (public Job Board API)."""

import json
import logging
from urllib.parse import quote

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{job_board_name}"


def _location(item: dict) -> str:
    names = [item.get("location")]
    names += [extra.get("location") for extra in item.get("secondaryLocations") or []]
    text = ", ".join(name for name in names if name)
    if item.get("isRemote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _description(item: dict) -> str:
    parts = []
    for field, label in [("department", "Department"), ("team", "Team"), ("employmentType", "Employment")]:
        value = item.get(field)
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def scrape(company_name: str, job_board_name: str) -> list[Job]:
    url = API_URL.format(job_board_name=quote(job_board_name))
    data = json.loads(fetch_html(url))

    jobs = []
    for item in data["jobs"]:
        if item.get("isListed") is False:
            continue
        jobs.append(
            Job(
                company=company_name,
                title=item["title"],
                location=_location(item),
                url=item["jobUrl"],
                source="ashby",
                description=_description(item),
            )
        )

    if not jobs:
        logger.warning(
            "ashby (%s): found 0 jobs. Check the job_board_name \"%s\".",
            company_name,
            job_board_name,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("IT Labs", "IT Labs")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.description} | {job.url}")
    print(f"Total jobs: {len(found_jobs)}")
