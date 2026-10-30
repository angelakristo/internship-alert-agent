"""Generic scraper for companies that use the TalentLyft ATS (career site JobList)."""

# logging служи за печатење пораки и предупредувања.
import logging

# re (регуларни изрази) ни треба за да ги прочитаме поставките од почетната страница.
import re

# time.sleep ни треба за пауза меѓу барањата.
import time

# urlencode ги составува параметрите за url, а urljoin прави апсолутни линкови.
from urllib.parse import urlencode, urljoin

# requests го користиме директно, бидејќи JobList бара дополнителен header
# што fetch_html не го праќа.
import requests

# BeautifulSoup ни помага да го пребаруваме HTML-от.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import TIMEOUT_SECONDS, USER_AGENT, fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Колку огласи да бараме по страница.
PAGE_SIZE = 50

# Најмногу колку страници да прочитаме.
MAX_PAGES = 10

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме сајтот.
PAUSE_SECONDS = 2


def _read_settings(base_url: str) -> dict:
    """Ги чита поставките на career страницата што се потребни за JobList.

    TalentLyft ги запишува во почетната страница, во JavaScript објект
    „initialData“, на пр.: subdomain: 'htecgroup', themeId: '2', layoutId: 'Jobs-1'.
    """
    html = fetch_html(base_url)
    settings = {}
    for key in ["subdomain", "themeId", "language", "layoutId"]:
        # Бараме текст од типот: key: 'вредност'
        match = re.search(rf"{key}:\s*'([^']*)'", html)
        if match is None:
            raise RuntimeError(f"TalentLyft: не најдов „{key}“ на {base_url}")
        settings[key] = match.group(1)
    return settings


def _fetch_job_list(base_url: str, settings: dict, page: int) -> str:
    """Симнува една страница од листата огласи (HTML фрагмент)."""
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
        # Без X-Requested-With серверот враќа 404 (ја очекува како барање од JavaScript).
        headers={"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest"},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Неуспешно симнување на JobList од {base_url}: статус {response.status_code}")
    return response.text


def scrape(company_name: str, career_domain: str) -> list[Job]:
    """Ги симнува огласите на една компанија од TalentLyft и ги враќа како листа од Job."""
    # Дозволуваме доменот да е запишан и со "https://" и со "/" на крајот.
    domain = career_domain.removeprefix("https://").removeprefix("http://").rstrip("/")
    base_url = f"https://{domain}"

    # 1. Ги читаме поставките од почетната страница.
    settings = _read_settings(base_url)

    jobs = []
    # Паметиме кои линкови веќе ги додадовме, за ист оглас да не се појави двапати.
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):
        # Пауза пред секое барање (и пред првата страница, по почетната).
        time.sleep(PAUSE_SECONDS)

        # 2. Ја симнуваме страницата и ја претвораме во објект што може да се пребарува.
        soup = BeautifulSoup(_fetch_job_list(base_url, settings, page), "html.parser")

        # 3. Секој оглас е линк со класа "jobs__box".
        for box in soup.select("a.jobs__box"):
            heading = box.select_one(".jobs__box__heading")
            if heading is None:
                continue
            url = urljoin(base_url, box.get("href", ""))
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Локацијата е под насловот. TalentLyft веќе додава „(Remote)“
            # или „(Hybrid)“ на крајот, на пр. "Warszawa, Poland (Remote)".
            location_tag = box.select_one(".jobs__box__text")
            location = location_tag.get_text(" ", strip=True) if location_tag else ""

            jobs.append(
                Job(
                    company=company_name,
                    title=heading.get_text(strip=True),
                    location=location,
                    url=url,
                    source="talentlyft",
                    # Листата нема податок за оддел, па описот останува празен.
                    description="",
                )
            )

        # 4. Страничењето: линковите имаат data-page="1", "2" ...
        #    Ако нема поголем број од тековната страница, тоа е последната.
        page_numbers = [
            int(link["data-page"])
            for link in soup.select(".pagination a[data-page]")
            if link["data-page"].isdigit()
        ]
        if not page_numbers or max(page_numbers) <= page:
            break

    # Ако нема ниту еден оглас, можеби компанијата навистина нема огласи,
    # но можеби и доменот е погрешен или страницата е сменета.
    if not jobs:
        logger.warning(
            "talentlyft (%s): пронајдени се 0 огласи. Провери го career_domain „%s“.",
            company_name,
            career_domain,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.talentlyft
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("HTEC", "careers.htecgroup.com")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
