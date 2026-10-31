"""Scraper for vrabotuvanje.com.mk (keyword search for internship postings)."""

import logging
import time
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.vrabotuvanje.com.mk/prebaruvanje-na-rabotni-mesta"

SEARCH_WORDS = ["пракса", "практикант", "стажант", "intern", "internship", "trainee"]

PAUSE_SECONDS = 2


def _clean_url(href: str) -> str:
    absolute = urljoin(SEARCH_URL, href)
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _is_real_result(href: str) -> bool:
    query = parse_qs(urlsplit(href).query)
    return query.get("source") == ["search_results"]


def scrape() -> list[Job]:
    jobs = []
    seen_urls = set()
    total_cards = 0

    for index, word in enumerate(SEARCH_WORDS):
        if index > 0:
            time.sleep(PAUSE_SECONDS)

        html = fetch_html(f"{SEARCH_URL}?query={quote(word)}")

        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select(".job-card")
        total_cards += len(cards)

        for card in cards:
            title_tag = card.select_one('[data-test="job-card-content-title"]')
            link = card.select_one('a[href^="/rabota/"]')
            if title_tag is None or link is None:
                continue

            if not _is_real_result(link["href"]):
                continue

            title = title_tag.get_text(strip=True)
            url = _clean_url(link["href"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            logo = card.select_one(".logo-container img[alt]")
            company = logo["alt"].strip() if logo else ""

            location_tag = card.select_one(".info__child:not(.info__end-date)")
            location = location_tag.get_text(strip=True) if location_tag else ""

            jobs.append(
                Job(
                    company=company,
                    title=title,
                    location=location,
                    url=url,
                    source="vrabotuvanje",
                )
            )

    if total_cards == 0:
        logger.warning(
            "vrabotuvanje: пронајдени се 0 огласи. Селекторите можеби се застарени "
            "– провери ја структурата на %s",
            SEARCH_URL,
        )

    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
