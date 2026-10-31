"""Scraper for the CodeChem Careers page (codechem.com/careers/open-positions)."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

CAREERS_URL = "https://codechem.com/careers/open-positions"


def scrape() -> list[Job]:
    html = fetch_html(CAREERS_URL)

    soup = BeautifulSoup(html, "html.parser")

    links = soup.select('a[href^="/positions/"]')

    jobs = []
    seen_urls = set()
    for link in links:
        heading = link.find("h1")
        if heading is None:
            continue

        url = urljoin(CAREERS_URL, link["href"])
        if url in seen_urls:
            continue
        seen_urls.add(url)

        details = [span.get_text(strip=True) for span in link.find_all("span")]
        details = [text for text in details if text]

        if len(details) >= 2:
            location = details[-1]
            description = ", ".join(details[:-1])
        else:
            location = ""
            description = ", ".join(details)

        jobs.append(
            Job(
                company="CodeChem",
                title=heading.get_text(strip=True),
                location=location,
                url=url,
                source="codechem_site",
                description=description,
            )
        )

    if not jobs:
        logger.warning(
            "CodeChem: found 0 jobs. The selectors may be outdated "
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
