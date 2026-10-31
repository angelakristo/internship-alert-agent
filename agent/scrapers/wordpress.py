"""Generic scraper for company career sites built on WordPress (REST API)."""

# json го претвора текстот од API-то во Python речници и листи.
import json

# logging служи за печатење пораки.
import logging

# time.sleep ни треба за пауза меѓу барањата.
import time

# datetime и timedelta ни требаат за да пресметаме „пред 60 дена“.
from datetime import datetime, timedelta, timezone

# urlencode ги составува параметрите за url.
from urllib.parse import urlencode

# BeautifulSoup ни помага да ги тргнеме HTML таговите и ентитетите (на пр. &amp;).
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# WordPress REST API: секој тип на објава (на пр. "jobs") има своја адреса.
API_URL = "https://{domain}/wp-json/wp/v2/{post_type}?{query}"

# Земаме само огласи објавени или изменети во последните толку дена.
# WordPress API-то ги враќа и старите огласи, а нив не ги сакаме.
MAX_AGE_DAYS = 60

# Колку огласи по страница (100 е најмногу што WordPress дозволува).
PAGE_SIZE = 100

# Најмногу колку страници да прочитаме.
MAX_PAGES = 5

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме сајтот.
PAUSE_SECONDS = 2

# Најмногу колку карактери од описот да зачуваме.
MAX_DESCRIPTION_LENGTH = 500


def _plain_text(html: str) -> str:
    """Го претвора HTML-от во обичен текст: без тагови, без ентитети, без вишок празни места."""
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return " ".join(text.split())


def scrape(company_name: str, domain: str, post_type: str) -> list[Job]:
    """Ги симнува новите огласи од WordPress сајт на компанија и ги враќа како листа од Job."""
    # Дозволуваме доменот да е запишан и со "https://" и со "/" на крајот.
    domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")

    # Граница: сè што е изменето пред овој момент го прескокнуваме.
    # Секоја објава е „изменета“ најмалку кога е објавена, па modified_after
    # ги опфаќа и новообјавените и неодамна изменетите огласи.
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    jobs = []
    for page in range(1, MAX_PAGES + 1):
        # Пауза пред секое барање освен првото.
        if page > 1:
            time.sleep(PAUSE_SECONDS)

        query = urlencode({
            "per_page": PAGE_SIZE,
            "page": page,
            # Серверот сам ги филтрира старите огласи (WordPress 5.7 и понов).
            "modified_after": cutoff.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        # fetch_html го враќа одговорот како текст, а json.loads го претвора во листа.
        items = json.loads(fetch_html(API_URL.format(domain=domain, post_type=post_type, query=query)))

        for item in items:
            # За секој случај проверуваме и во кодот, ако постара верзија на
            # WordPress го игнорира параметарот modified_after.
            modified = datetime.fromisoformat(item.get("modified_gmt") or item["date_gmt"])
            if modified.replace(tzinfo=timezone.utc) < cutoff:
                continue

            # За опис го земаме краткиот извадок (excerpt), а ако го нема – содржината.
            summary = (item.get("excerpt") or {}).get("rendered") or (item.get("content") or {}).get("rendered") or ""

            jobs.append(
                Job(
                    company=company_name,
                    # Насловот може да има HTML ентитети (на пр. "F&amp;O" → "F&O").
                    title=_plain_text(item["title"]["rendered"]),
                    # WordPress нема стандардно поле за локација, па останува празна.
                    location="",
                    url=item["link"],
                    source="wordpress",
                    description=_plain_text(summary)[:MAX_DESCRIPTION_LENGTH],
                )
            )

        # Ако страницата не е полна, тоа е последната.
        # (Барање за страница по последната WordPress го враќа како грешка.)
        if len(items) < PAGE_SIZE:
            break

    # Кај овие сајтови е нормално да нема нови огласи, па само INFO порака.
    if not jobs:
        logger.info(
            "wordpress (%s): нема огласи од последните %d дена.",
            company_name,
            MAX_AGE_DAYS,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.wordpress
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат пораките.
    logging.basicConfig(level=logging.INFO)

    for name, site, kind in [
        ("Solutionade", "www.solutionade.net", "jobpost"),
        ("AXM365", "careers.axm365.com", "jobs"),
    ]:
        found_jobs = scrape(name, site, kind)
        for job in found_jobs:
            print(f"- {job.title} | {job.company} | {job.url} | {job.description[:80]}")
        print(f"{name}: вкупно огласи: {len(found_jobs)}")
