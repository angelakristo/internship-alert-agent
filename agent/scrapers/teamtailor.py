"""Generic scraper for companies that use the Teamtailor ATS (public jobs.json feed)."""

import json
import logging
import time

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

FEED_URL = "https://{career_domain}/jobs.json?page={page}"

MAX_PAGES = 10

PAUSE_SECONDS = 2


def _location(posting: dict) -> str:
    places = []
    for place in posting.get("jobLocation") or []:
        address = place.get("address") or {}
        parts = [address.get("addressLocality"), address.get("addressRegion") or address.get("addressCountry")]
        text = ", ".join(part.strip() for part in parts if part and part.strip())
        if text:
            places.append(text)
    location = "; ".join(places)

    if posting.get("jobLocationType") == "TELECOMMUTE":
        location = f"{location} (Remote)" if location else "Remote"
    return location


def _description(posting: dict) -> str:
    employment = posting.get("employmentType")
    if isinstance(employment, list):
        employment = ", ".join(employment)
    return f"Employment: {employment}" if employment else ""


def scrape(company_name: str, career_domain: str) -> list[Job]:
    domain = career_domain.removeprefix("https://").removeprefix("http://").rstrip("/")

    jobs = []
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(PAUSE_SECONDS)

        data = json.loads(fetch_html(FEED_URL.format(career_domain=domain, page=page)))

        new_on_page = 0
        for item in data.get("items") or []:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            new_on_page += 1

            posting = item.get("_jobposting") or {}
            jobs.append(
                Job(
                    company=company_name,
                    title=item["title"],
                    location=_location(posting),
                    url=url,
                    source="teamtailor",
                    description=_description(posting),
                )
            )

        if new_on_page == 0:
            break

    if not jobs:
        logger.warning(
            "teamtailor (%s): пронајдени се 0 огласи. Провери го career_domain „%s“.",
            company_name,
            career_domain,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("Nion", "career.nionit.com")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
