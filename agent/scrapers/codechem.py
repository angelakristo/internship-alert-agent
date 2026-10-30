"""Scraper for the CodeChem Careers page (codechem.com/careers/open-positions)."""

# logging служи за печатење пораки и предупредувања.
import logging

# urljoin спојува основен url со релативен линк (на пр. "/positions/...").
from urllib.parse import urljoin

# BeautifulSoup ни помага да го пребаруваме HTML-от.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Страницата со сите отворени огласи на CodeChem.
CAREERS_URL = "https://codechem.com/careers/open-positions"


def scrape() -> list[Job]:
    """Ги симнува огласите од CodeChem и ги враќа како листа од Job."""
    # 1. Го симнуваме HTML-от од страницата.
    html = fetch_html(CAREERS_URL)

    # 2. Го претвораме HTML-от во објект што може да се пребарува.
    soup = BeautifulSoup(html, "html.parser")

    # 3. Секој оглас е линк што почнува со "/positions/".
    links = soup.select('a[href^="/positions/"]')

    jobs = []
    # Паметиме кои линкови веќе ги додадовме, за ист оглас да не се појави двапати.
    seen_urls = set()
    for link in links:
        # Насловот е во <h1> внатре во линкот. Ако го нема, го прескокнуваме.
        heading = link.find("h1")
        if heading is None:
            continue

        # Линкот е релативен ("/positions/..."), па го правиме апсолутен.
        url = urljoin(CAREERS_URL, link["href"])
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Под насловот има неколку <span> со текст, на пр.:
        # "Junior", "Full-time", "Skopje, N. Macedonia".
        # Меѓу нив има и празни <span> (точките), па ги земаме само оние со текст.
        details = [span.get_text(strip=True) for span in link.find_all("span")]
        details = [text for text in details if text]

        # Последниот податок е локацијата, а останатите (ниво, тип) се описот.
        # Ако има само еден податок, не знаеме дали е локација, па локацијата е празна.
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

    # Ако не најдовме ниту еден оглас, најверојатно страницата е сменета.
    if not jobs:
        logger.warning(
            "CodeChem: пронајдени се 0 огласи. Селекторите можеби се застарени "
            "– провери ја структурата на %s",
            CAREERS_URL,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.codechem
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
