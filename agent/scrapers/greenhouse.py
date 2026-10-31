"""Generic scraper for companies that use the Greenhouse ATS (public JSON API)."""

import json
import logging
from urllib.parse import quote

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"

MAX_DESCRIPTION_LENGTH = 500


def _plain_text(content: str) -> str:
    unescaped = BeautifulSoup(content, "html.parser").get_text()
    text = BeautifulSoup(unescaped, "html.parser").get_text(" ")
    text = " ".join(text.split())
    return text[:MAX_DESCRIPTION_LENGTH]


def scrape(company_name: str, board_token: str) -> list[Job]:
    url = API_URL.format(board_token=quote(board_token))
    data = json.loads(fetch_html(url))

    jobs = []
    for item in data["jobs"]:
        jobs.append(
            Job(
                company=company_name,
                title=item["title"],
                location=(item.get("location") or {}).get("name", ""),
                url=item["absolute_url"],
                source="greenhouse",
                description=_plain_text(item.get("content") or ""),
            )
        )

    if not jobs:
        logger.warning(
            "greenhouse (%s): found 0 jobs. Check the board token \"%s\".",
            company_name,
            board_token,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("Loka", "lokainc")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Total jobs: {len(found_jobs)}")
