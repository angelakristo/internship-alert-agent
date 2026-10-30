"""Scraper for vrabotuvanje.com.mk (keyword search for internship postings)."""

# logging служи за печатење пораки и предупредувања.
import logging

# time.sleep ни треба за пауза меѓу барањата.
import time

# urljoin спојува основен url со релативен линк, urlsplit/urlunsplit ни помагаат
# да го тргнеме делот "?source=..." од линкот, parse_qs го чита тој дел,
# а quote ги кодира зборовите (на пр. кирилица) за да можат да одат во url.
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit

# BeautifulSoup ни помага да го пребаруваме HTML-от.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Сајтот нема категории (на пр. IT), па го користиме неговото пребарување
# по клучен збор: SEARCH_URL + "?query=<збор>".
SEARCH_URL = "https://www.vrabotuvanje.com.mk/prebaruvanje-na-rabotni-mesta"

# Зборовите што ги пребаруваме. Резултатите од сите се спојуваат без дупликати.
SEARCH_WORDS = ["пракса", "практикант", "стажант", "intern", "internship", "trainee"]

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме сајтот.
PAUSE_SECONDS = 2


def _clean_url(href: str) -> str:
    """Прави апсолутен линк и го трга "?source=..." од крајот.

    Без "?source=..." линкот е секогаш ист за ист оглас, па и job_id е стабилен.
    """
    absolute = urljoin(SEARCH_URL, href)
    parts = urlsplit(absolute)
    # Го задржуваме сè освен query делот (?...) и fragment делот (#...).
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _is_real_result(href: str) -> bool:
    """True ако огласот е вистински резултат од пребарувањето.

    Под резултатите сајтот додава и „препорачани“ огласи што немаат врска
    со зборот. Тие имаат source=search_results_recommendations во линкот,
    а вистинските резултати имаат source=search_results.
    """
    query = parse_qs(urlsplit(href).query)
    return query.get("source") == ["search_results"]


def scrape() -> list[Job]:
    """Го пребарува vrabotuvanje.com.mk за секој збор и ги враќа огласите како листа од Job."""
    jobs = []
    # Паметиме кои линкови веќе ги додадовме, за ист оглас да не се појави двапати
    # (на пр. ако го најдат и "пракса" и "intern").
    seen_urls = set()
    # Вкупен број на картички (заедно со препорачаните), за да знаеме дали
    # селекторите воопшто работат.
    total_cards = 0

    for index, word in enumerate(SEARCH_WORDS):
        # Пауза пред секое барање освен првото.
        if index > 0:
            time.sleep(PAUSE_SECONDS)

        # 1. Го симнуваме HTML-от од пребарувањето за овој збор.
        html = fetch_html(f"{SEARCH_URL}?query={quote(word)}")

        # 2. Го претвораме HTML-от во објект што може да се пребарува.
        soup = BeautifulSoup(html, "html.parser")

        # 3. Секој оглас е во елемент со класа "job-card".
        cards = soup.select(".job-card")
        total_cards += len(cards)

        for card in cards:
            # Насловот е во <h3 data-test="job-card-content-title">,
            # а линкот е <a> околу него.
            title_tag = card.select_one('[data-test="job-card-content-title"]')
            link = card.select_one('a[href^="/rabota/"]')
            if title_tag is None or link is None:
                continue

            # Ги прескокнуваме „препорачаните“ огласи.
            if not _is_real_result(link["href"]):
                continue

            title = title_tag.get_text(strip=True)
            url = _clean_url(link["href"])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Името на компанијата е запишано во alt текстот на логото.
            logo = card.select_one(".logo-container img[alt]")
            company = logo["alt"].strip() if logo else ""

            # Локацијата е првиот податок под насловот. Го прескокнуваме
            # „Пријава до ...“, кој има дополнителна класа info__end-date.
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

    # Нормално е да нема резултати за пракса, но ако нема ниту една картичка
    # (дури ни препорачана), најверојатно страницата е сменета.
    if total_cards == 0:
        logger.warning(
            "vrabotuvanje: пронајдени се 0 огласи. Селекторите можеби се застарени "
            "– провери ја структурата на %s",
            SEARCH_URL,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.vrabotuvanje
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
