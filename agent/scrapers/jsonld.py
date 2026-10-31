"""Generic scraper for career pages that publish schema.org JobPosting data (JSON-LD)."""

import json
import logging
import re
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

MAX_DETAIL_PAGES = 30

PAUSE_SECONDS = 1

MAX_DESCRIPTION_LENGTH = 500

JOB_LINK_PATTERN = re.compile(r"/(jobs?|careers?|positions?|vacanc(y|ies)|openings?|oglas\w*)/", re.IGNORECASE)


def _plain_text(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return " ".join(text.split())


def _is_job_posting(data: dict) -> bool:
    kind = data.get("@type")
    if isinstance(kind, list):
        return "JobPosting" in kind
    return kind == "JobPosting"


def _find_job_postings(data) -> list[dict]:
    found = []
    if isinstance(data, list):
        for element in data:
            found.extend(_find_job_postings(element))
    elif isinstance(data, dict):
        if _is_job_posting(data):
            found.append(data)
        else:
            for value in data.values():
                found.extend(_find_job_postings(value))
    return found


def _job_postings_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text())
        except json.JSONDecodeError:
            continue
        postings.extend(_find_job_postings(data))
    return postings


def _location(posting: dict) -> str:
    places = posting.get("jobLocation") or []
    if isinstance(places, dict):
        places = [places]

    parts = []
    for place in places:
        address = place.get("address") if isinstance(place, dict) else None
        if isinstance(address, str):
            parts.append(address.strip())
        elif isinstance(address, dict):
            country = address.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            text = ", ".join(str(part).strip() for part in [address.get("addressLocality"), country] if part)
            if text:
                parts.append(text)
    location = "; ".join(parts)

    if posting.get("jobLocationType") == "TELECOMMUTE":
        location = f"{location} (Remote)" if location else "Remote"
    return location


def _description(posting: dict) -> str:
    text = _plain_text(str(posting.get("description") or ""))
    if not text:
        employment = posting.get("employmentType")
        if isinstance(employment, list):
            employment = ", ".join(employment)
        text = f"Employment: {employment}" if employment else ""
    return text[:MAX_DESCRIPTION_LENGTH]


def _job_links(html: str, careers_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlsplit(careers_url).netloc
    links = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(careers_url, anchor["href"]).split("#")[0]
        if urlsplit(url).netloc != host or url.rstrip("/") == careers_url.rstrip("/"):
            continue
        if JOB_LINK_PATTERN.search(urlsplit(url).path + "/") and url not in links:
            links.append(url)
    return links[:MAX_DETAIL_PAGES]


def scrape(company_name: str, careers_url: str) -> list[Job]:
    html = fetch_html(careers_url)
    found = [(posting, careers_url) for posting in _job_postings_from_html(html)]

    if not found:
        for index, link in enumerate(_job_links(html, careers_url)):
            if index > 0:
                time.sleep(PAUSE_SECONDS)
            try:
                page_html = fetch_html(link)
            except Exception:
                logger.warning("jsonld (%s): не можам да го отворам %s", company_name, link)
                continue
            found.extend((posting, link) for posting in _job_postings_from_html(page_html))

    jobs = []
    seen_urls = set()
    for posting, page_url in found:
        title = _plain_text(str(posting.get("title") or ""))
        if not title:
            continue
        url = urljoin(page_url, str(posting.get("url") or page_url))
        if (url, title) in seen_urls:
            continue
        seen_urls.add((url, title))

        jobs.append(
            Job(
                company=company_name,
                title=title,
                location=_location(posting),
                url=url,
                source="jsonld",
                description=_description(posting),
            )
        )

    if not jobs:
        logger.warning(
            "jsonld (%s): пронајдени се 0 огласи. Провери дали %s сè уште има JobPosting податоци.",
            company_name,
            careers_url,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("vector8", "https://www.vector8.com/en/careers")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
