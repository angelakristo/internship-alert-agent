"""Scraper for the SORSIX Careers page (sorsix.com/company/careers)."""

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

# Страницата со огласите на SORSIX.
CAREERS_URL = "https://www.sorsix.com/company/careers"

# Текстот што SORSIX го прикажува кога нема отворени позиции.
NO_POSITIONS_TEXT = "We currently do not have any open positions"


def _parse_html(html: str) -> list[Job]:
    """Ги чита огласите од HTML-от на страницата.

    Посебна функција е за да може да се тестира и со пример HTML, без интернет.
    """
    # 1. Ако SORSIX пишува дека нема позиции, тоа е нормално – само INFO порака.
    if NO_POSITIONS_TEXT in html:
        logger.info("SORSIX: моментално нема отворени позиции.")
        return []

    # 2. Го претвораме HTML-от во објект што може да се пребарува.
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    # Паметиме кои огласи веќе ги додадовме, за ист оглас да не се појави двапати.
    seen = set()
    # Секој оглас е ред (<tr>) во табелата со класа "openings-table".
    # Точната структура на редот не ја знаеме (табелата досега беше празна),
    # па претпоставуваме: прва колона = наслов, втора колона = локација.
    for row in soup.select(".openings-table tr"):
        # Редот со заглавија (<th>) го прескокнуваме.
        cells = row.find_all("td")
        if not cells:
            continue

        title = cells[0].get_text(" ", strip=True)
        if not title:
            continue
        location = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""

        # Ако во редот има вистински линк, го користиме; инаку careers страницата.
        # Линковите "#..." и "javascript:..." не водат до посебна страница.
        url = CAREERS_URL
        link = row.find("a", href=True)
        if link and not link["href"].startswith(("#", "javascript:")):
            url = urljoin(CAREERS_URL, link["href"])

        if (title, url) in seen:
            continue
        seen.add((title, url))

        jobs.append(
            Job(
                company="SORSIX",
                title=title,
                location=location,
                url=url,
                source="sorsix_site",
            )
        )

    # 3. Текстот „нема позиции“ го нема, а не најдовме ниту еден оглас:
    #    SORSIX веројатно објавил позиции во структура што не ја препознаваме.
    #    Фрламе исклучок за main.py да заврши со код 1 и GitHub Actions да те извести.
    if not jobs:
        raise RuntimeError("SORSIX објави позиции, но scraper-от не ги препозна – провери рачно")

    return jobs


def scrape() -> list[Job]:
    """Ги симнува огласите од SORSIX и ги враќа како листа од Job."""
    return _parse_html(fetch_html(CAREERS_URL))


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.sorsix
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат пораките.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
