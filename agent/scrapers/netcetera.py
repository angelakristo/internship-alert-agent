"""Scraper for the Netcetera Careers page (netcetera.com/careers/open-positions)."""

# logging служи за печатење пораки и предупредувања.
import logging

# urljoin спојува основен url со релативен линк (на пр. "/careers/...").
from urllib.parse import urljoin

# BeautifulSoup ни помага да го пребаруваме HTML-от.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Страницата со сите отворени огласи на Netcetera.
CAREERS_URL = "https://www.netcetera.com/careers/open-positions"


def scrape() -> list[Job]:
    """Ги симнува огласите од Netcetera и ги враќа како листа од Job."""
    # 1. Го симнуваме HTML-от од страницата.
    html = fetch_html(CAREERS_URL)

    # 2. Го претвораме HTML-от во објект што може да се пребарува.
    soup = BeautifulSoup(html, "html.parser")

    # 3. Ги наоѓаме сите картички со огласи.
    #    Секоја картичка има атрибут data-jobs-filter-item.
    cards = soup.select("[data-jobs-filter-item]")

    jobs = []
    for card in cards:
        # Линкот до огласот е во <a> таг. Ако го нема, ја прескокнуваме картичката.
        link = card.find("a")
        if link is None:
            continue

        # Насловот е текстот на линкот (strip ги брише празните места на краевите).
        title = link.get_text(strip=True)

        # Линкот е релативен ("/careers/..."), па го правиме апсолутен.
        url = urljoin(CAREERS_URL, link.get("href", ""))

        # Државата е запишана во атрибутот data-country (на пр. "MK").
        location = card.get("data-country", "")

        # Одделот е во badge-от. Ако го нема, description останува празен.
        badge = card.select_one(".news-card__badge")
        description = badge.get_text(strip=True) if badge else ""

        # Го креираме Job објектот и го додаваме во листата.
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

    # Ако не најдовме ниту еден оглас, најверојатно страницата е сменета.
    if not jobs:
        logger.warning(
            "Netcetera: пронајдени се 0 огласи. Селекторите можеби се застарени "
            "– провери ја структурата на %s",
            CAREERS_URL,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.netcetera
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
