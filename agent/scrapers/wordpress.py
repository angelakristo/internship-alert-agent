"""Generic scraper for company career sites built on WordPress (REST API)."""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

API_URL = "https://{domain}/wp-json/wp/v2/{post_type}?{query}"

MAX_AGE_DAYS = 60

PAGE_SIZE = 100

MAX_PAGES = 5

PAUSE_SECONDS = 2

MAX_DESCRIPTION_LENGTH = 500


def _plain_text(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return " ".join(text.split())


def scrape(company_name: str, domain: str, post_type: str) -> list[Job]:
    domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    jobs = []
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(PAUSE_SECONDS)

        query = urlencode({
            "per_page": PAGE_SIZE,
            "page": page,
            "modified_after": cutoff.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        items = json.loads(fetch_html(API_URL.format(domain=domain, post_type=post_type, query=query)))

        for item in items:
            modified = datetime.fromisoformat(item.get("modified_gmt") or item["date_gmt"])
            if modified.replace(tzinfo=timezone.utc) < cutoff:
                continue

            summary = (item.get("excerpt") or {}).get("rendered") or (item.get("content") or {}).get("rendered") or ""

            jobs.append(
                Job(
                    company=company_name,
                    title=_plain_text(item["title"]["rendered"]),
                    location="",
                    url=item["link"],
                    source="wordpress",
                    description=_plain_text(summary)[:MAX_DESCRIPTION_LENGTH],
                )
            )

        if len(items) < PAGE_SIZE:
            break

    if not jobs:
        logger.info(
            "wordpress (%s): no jobs from the last %d days.",
            company_name,
            MAX_AGE_DAYS,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    for name, site, kind in [
        ("Solutionade", "www.solutionade.net", "jobpost"),
        ("AXM365", "careers.axm365.com", "jobs"),
    ]:
        found_jobs = scrape(name, site, kind)
        for job in found_jobs:
            print(f"- {job.title} | {job.company} | {job.url} | {job.description[:80]}")
        print(f"{name}: total jobs: {len(found_jobs)}")
