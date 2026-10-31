"""Scraper for the SORSIX Careers page (sorsix.com/company/careers)."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

CAREERS_URL = "https://www.sorsix.com/company/careers"

NO_POSITIONS_TEXT = "We currently do not have any open positions"


def _parse_html(html: str) -> list[Job]:
    if NO_POSITIONS_TEXT in html:
        logger.info("SORSIX: no open positions at the moment.")
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    seen = set()
    for row in soup.select(".openings-table tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        title = cells[0].get_text(" ", strip=True)
        if not title:
            continue
        location = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""

        url = CAREERS_URL
        link = row.find("a", href=True)
        if link and not link["href"].startswith(("#", "javascript:")):
            url = urljoin(CAREERS_URL, link["href"])

        if (title, url) in seen:
            continue
        seen.add((title, url))

        jobs.append(
            Job(
                company="SORSIX",
                title=title,
                location=location,
                url=url,
                source="sorsix_site",
            )
        )

    if not jobs:
        raise RuntimeError("SORSIX published positions, but the scraper did not recognize them – check manually")

    return jobs


def scrape() -> list[Job]:
    return _parse_html(fetch_html(CAREERS_URL))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.location} | {job.url}")
    print(f"Total jobs: {len(found_jobs)}")
