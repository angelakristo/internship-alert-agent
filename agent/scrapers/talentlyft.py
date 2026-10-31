"""Generic scraper for companies that use the TalentLyft ATS (career site JobList)."""

import logging
import re
import time
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import TIMEOUT_SECONDS, USER_AGENT, fetch_html

logger = logging.getLogger(__name__)

PAGE_SIZE = 50

MAX_PAGES = 10

PAUSE_SECONDS = 2


def _read_settings(base_url: str) -> dict:
    html = fetch_html(base_url)
    settings = {}
    for key in ["subdomain", "themeId", "language", "layoutId"]:
        match = re.search(rf"{key}:\s*'([^']*)'", html)
        if match is None:
            raise RuntimeError(f"TalentLyft: could not find \"{key}\" on {base_url}")
        settings[key] = match.group(1)
    return settings


def _fetch_job_list(base_url: str, settings: dict, page: int) -> str:
    params = {
        "layoutId": settings["layoutId"],
        "websiteUrl": base_url,
        "themeId": settings["themeId"],
        "language": settings["language"],
        "subdomain": settings["subdomain"],
        "page": page,
        "pageSize": PAGE_SIZE,
        "contains": "",
    }
    response = requests.get(
        f"{base_url}/JobList?{urlencode(params)}",
        headers={"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest"},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to download JobList from {base_url}: status {response.status_code}")
    return response.text


def scrape(company_name: str, career_domain: str) -> list[Job]:
    domain = career_domain.removeprefix("https://").removeprefix("http://").rstrip("/")
    base_url = f"https://{domain}"

    settings = _read_settings(base_url)

    jobs = []
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):
        time.sleep(PAUSE_SECONDS)

        soup = BeautifulSoup(_fetch_job_list(base_url, settings, page), "html.parser")

        for box in soup.select("a.jobs__box"):
            heading = box.select_one(".jobs__box__heading")
            if heading is None:
                continue
            url = urljoin(base_url, box.get("href", ""))
            if url in seen_urls:
                continue
            seen_urls.add(url)

            location_tag = box.select_one(".jobs__box__text")
            location = location_tag.get_text(" ", strip=True) if location_tag else ""

            jobs.append(
                Job(
                    company=company_name,
                    title=heading.get_text(strip=True),
                    location=location,
                    url=url,
                    source="talentlyft",
                    description="",
                )
            )

        page_numbers = [
            int(link["data-page"])
            for link in soup.select(".pagination a[data-page]")
            if link["data-page"].isdigit()
        ]
        if not page_numbers or max(page_numbers) <= page:
            break

    if not jobs:
        logger.warning(
            "talentlyft (%s): found 0 jobs. Check the career_domain \"%s\".",
            company_name,
            career_domain,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("HTEC", "careers.htecgroup.com")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Total jobs: {len(found_jobs)}")
