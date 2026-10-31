"""Scraper for Joberty (joberty.com) using its public JSON API."""

import json
import logging
import time
from urllib.parse import quote, urlencode

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

API_URL = "https://backend.joberty.com/api/v1/jobs"

JOB_PAGE_URL = "https://www.joberty.com/job"

PAGE_SIZE = 100

PAUSE_SECONDS = 2

SEARCHES = [
    ({"seniority": "Internship", "location": "North Macedonia"}, "Seniority: Internship"),
    ({"location": "North Macedonia"}, ""),
]


def _job_url(item: dict) -> str:
    slug = item["jobTitle"].replace("#", "").lower()
    for character in [" ", "/", "\\"]:
        slug = slug.replace(character, "-")
    return f"{JOB_PAGE_URL}/{quote(item['companyUrlName'])}/{quote(slug)}/{item['id']}"


def _fetch_page(params: dict, page: int) -> dict:
    query = urlencode({**params, "page": page, "pageSize": PAGE_SIZE})
    return json.loads(fetch_html(f"{API_URL}?{query}"))


def scrape() -> list[Job]:
    jobs = []
    seen_urls = set()
    request_count = 0

    for params, description in SEARCHES:
        page = 0
        while True:
            if request_count > 0:
                time.sleep(PAUSE_SECONDS)
            request_count += 1

            data = _fetch_page(params, page)

            for item in data["items"]:
                url = _job_url(item)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                jobs.append(
                    Job(
                        company=item["companyName"],
                        title=item["jobTitle"],
                        location=", ".join(item.get("cities") or []),
                        url=url,
                        source="joberty",
                        description=description,
                    )
                )

            page += 1
            if page >= data["totalPage"]:
                break

    if not jobs:
        logger.warning(
            "joberty: пронајдени се 0 огласи. Можеби нема огласи за Македонија, "
            "или API-то е сменето – провери го %s",
            API_URL,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
