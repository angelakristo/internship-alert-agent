"""Scraper for the Netcetera Careers page (netcetera.com/careers/open-positions)."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

CAREERS_URL = "https://www.netcetera.com/careers/open-positions"


def scrape() -> list[Job]:
    html = fetch_html(CAREERS_URL)

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select("[data-jobs-filter-item]")

    jobs = []
    for card in cards:
        link = card.find("a")
        if link is None:
            continue

        title = link.get_text(strip=True)

        url = urljoin(CAREERS_URL, link.get("href", ""))

        location = card.get("data-country", "")

        badge = card.select_one(".news-card__badge")
        description = badge.get_text(strip=True) if badge else ""

        jobs.append(
            Job(
                company="Netcetera",
                title=title,
                location=location,
                url=url,
                source="netcetera_site",
                description=description,
            )
        )

    if not jobs:
        logger.warning(
            "Netcetera: found 0 jobs. The selectors may be outdated "
            "– check the structure of %s",
            CAREERS_URL,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.location} | {job.description} | {job.url}")
    print(f"Total jobs: {len(found_jobs)}")
