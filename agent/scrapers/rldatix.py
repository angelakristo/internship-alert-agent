"""Scraper for the RLDatix Careers page (North Macedonia roles)."""

# logging служи за печатење пораки и предупредувања.
import logging

# time.sleep ни треба за пауза меѓу барањата.
import time

# urljoin спојува основен url со релативен линк (на пр. "/jobs/...").
from urllib.parse import urljoin

# BeautifulSoup ни помага да го пребаруваме HTML-от.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Страницата со огласите на RLDatix за Северна Македонија.
CAREERS_URL = "https://careers.rldatix.com/jobs/search/north-macedonia-roles"

# Најмногу колку страници да прочитаме.
MAX_PAGES = 5

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме сајтот.
PAUSE_SECONDS = 2


def scrape() -> list[Job]:
    """Ги симнува огласите од RLDatix за Македонија и ги враќа како листа од Job."""
    jobs = []
    # Паметиме кои линкови веќе ги додадовме, за ист оглас да не се појави двапати.
    seen_urls = set()

    page_url = CAREERS_URL
    for page in range(MAX_PAGES):
        # Пауза пред секое барање освен првото.
        if page > 0:
            time.sleep(PAUSE_SECONDS)

        # 1. Го симнуваме HTML-от и го претвораме во објект што може да се пребарува.
        soup = BeautifulSoup(fetch_html(page_url), "html.parser")

        # 2. Секој оглас е ред во табела (<tr>) со атрибут data-job-url.
        for row in soup.select("tr[data-job-url]"):
            # Насловот е линкот во колоната со класа job-search-results-title.
            link = row.select_one(".job-search-results-title a")
            if link is None:
                continue

            # Линкот обично е веќе целосен, но за секој случај го правиме апсолутен.
            url = urljoin(page_url, link.get("href") or row["data-job-url"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Локациите се во листа (<li>), на пр. "Skopje, North Macedonia".
            locations = [li.get_text(strip=True) for li in row.select(".job-search-results-location li")]

            # Описот го составуваме од категоријата (на пр. "Development")
            # и типот на вработување (на пр. "Full Time"), ако ги има.
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

        # 3. Пагинација: ако постои линк „следна страница“ (rel="next"), продолжуваме.
        next_link = soup.select_one('a[rel="next"]')
        if next_link is None or not next_link.get("href"):
            break
        page_url = urljoin(page_url, next_link["href"])

    # Ако не најдовме ниту еден оглас, најверојатно страницата е сменета
    # (или RLDatix моментално нема огласи во Македонија).
    if not jobs:
        logger.warning(
            "RLDatix: пронајдени се 0 огласи. Селекторите можеби се застарени "
            "– провери ја структурата на %s",
            CAREERS_URL,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.rldatix
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
