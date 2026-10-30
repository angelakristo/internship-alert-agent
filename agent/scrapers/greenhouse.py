"""Generic scraper for companies that use the Greenhouse ATS (public JSON API)."""

# json го претвора текстот од API-то во Python речници и листи.
import json

# logging служи за печатење пораки и предупредувања.
import logging

# quote го кодира board token-от за да може безбедно да оди во url.
from urllib.parse import quote

# BeautifulSoup ни помага да ги тргнеме HTML таговите од описот.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Јавниот Greenhouse API. {board_token} е името на компанијата во Greenhouse
# (на пр. "lokainc"), а content=true го враќа и описот на огласот.
API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"

# Најмногу колку карактери од описот да зачуваме.
MAX_DESCRIPTION_LENGTH = 500


def _plain_text(content: str) -> str:
    """Го претвора описот од Greenhouse во обичен текст, без HTML тагови."""
    # Greenhouse го праќа HTML-от „заштитен“ (на пр. &lt;p&gt; наместо <p>).
    # BeautifulSoup прво го враќа во вистински HTML, па потоа ги трга таговите.
    unescaped = BeautifulSoup(content, "html.parser").get_text()
    text = BeautifulSoup(unescaped, "html.parser").get_text(" ")
    # Повеќе празни места и нови редови ги спојуваме во едно празно место.
    text = " ".join(text.split())
    return text[:MAX_DESCRIPTION_LENGTH]


def scrape(company_name: str, board_token: str) -> list[Job]:
    """Ги симнува огласите на една компанија од Greenhouse и ги враќа како листа од Job."""
    # 1. Го симнуваме JSON-от од API-то. fetch_html го враќа како текст,
    #    а json.loads го претвора во речник.
    url = API_URL.format(board_token=quote(board_token))
    data = json.loads(fetch_html(url))

    # 2. Секој оглас од листата "jobs" го претвораме во Job.
    jobs = []
    for item in data["jobs"]:
        jobs.append(
            Job(
                company=company_name,
                title=item["title"],
                # location е речник, на пр. {"name": "North Macedonia"}.
                location=(item.get("location") or {}).get("name", ""),
                # absolute_url е веќе целосен линк до огласот.
                url=item["absolute_url"],
                source="greenhouse",
                description=_plain_text(item.get("content") or ""),
            )
        )

    # Ако нема ниту еден оглас, можеби компанијата навистина нема огласи,
    # но можеби и board token-от е погрешен или сменет.
    if not jobs:
        logger.warning(
            "greenhouse (%s): пронајдени се 0 огласи. Провери го board token-от „%s“.",
            company_name,
            board_token,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.greenhouse
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("Loka", "lokainc")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
