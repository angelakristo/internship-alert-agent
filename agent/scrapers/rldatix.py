"""Scraper for the RLDatix Careers page (North Macedonia roles)."""

import logging
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

CAREERS_URL = "https://careers.rldatix.com/jobs/search/north-macedonia-roles"

MAX_PAGES = 5

PAUSE_SECONDS = 2


def scrape() -> list[Job]:
    jobs = []
    seen_urls = set()

    page_url = CAREERS_URL
    for page in range(MAX_PAGES):
        if page > 0:
            time.sleep(PAUSE_SECONDS)

        soup = BeautifulSoup(fetch_html(page_url), "html.parser")

        for row in soup.select("tr[data-job-url]"):
            link = row.select_one(".job-search-results-title a")
            if link is None:
                continue

            url = urljoin(page_url, link.get("href") or row["data-job-url"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            locations = [li.get_text(strip=True) for li in row.select(".job-search-results-location li")]

            categories = [li.get_text(strip=True) for li in row.select(".job-search-results-category li")]
            employment = row.select_one(".job-search-results-dropdown_field_1")
            parts = []
            if categories:
                parts.append(f"Category: {', '.join(categories)}")
            if employment and employment.get_text(strip=True):
                parts.append(f"Employment: {employment.get_text(strip=True)}")

            jobs.append(
                Job(
                    company="RLDatix",
                    title=link.get_text(strip=True),
                    location="; ".join(locations),
                    url=url,
                    source="rldatix_site",
                    description="; ".join(parts),
                )
            )

        next_link = soup.select_one('a[rel="next"]')
        if next_link is None or not next_link.get("href"):
            break
        page_url = urljoin(page_url, next_link["href"])

    if not jobs:
        logger.warning(
            "RLDatix: found 0 jobs. The selectors may be outdated "
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
