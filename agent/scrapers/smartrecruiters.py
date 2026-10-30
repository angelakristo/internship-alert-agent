"""Generic scraper for companies that use the SmartRecruiters ATS (public Postings API)."""

# json го претвора текстот од API-то во Python речници и листи.
import json

# logging служи за печатење пораки и предупредувања.
import logging

# time.sleep ни треба за пауза меѓу барањата.
import time

# quote го кодира company_id за да може безбедно да оди во url.
from urllib.parse import quote

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Јавниот SmartRecruiters Postings API. Филтер по држава намерно НЕ користиме,
# бидејќи може да има Remote огласи запишани во друга држава.
# Локацијата ја проверува agent/filters.py.
API_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings?limit={limit}&offset={offset}"

# Јавната страница на огласот: https://jobs.smartrecruiters.com/<компанија>/<id>
JOB_PAGE_URL = "https://jobs.smartrecruiters.com/{company}/{job_id}"

# Колку огласи по страница (100 е најмногу што API-то дозволува).
PAGE_SIZE = 100

# Најмногу колку страници да прочитаме (10 × 100 = 1000 огласи).
MAX_PAGES = 10

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме API-то.
PAUSE_SECONDS = 2


def _location(item: dict) -> str:
    """Ја составува локацијата: град, регион и држава, плус „Remote“ ако е далечинска работа."""
    location = item.get("location") or {}
    # fullLocation е на пр. "Skopje, Grad Skopje, North Macedonia".
    text = location.get("fullLocation") or ", ".join(
        part for part in [location.get("city"), location.get("country")] if part
    )
    if location.get("remote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _description(item: dict) -> str:
    """Краток опис од податоците што ги има во листата: оддел, функција и ниво.

    Нивото (на пр. „Internship“) е важно: така agent/filters.py препознава
    пракса дури и ако насловот не го содржи зборот „intern“.
    """
    parts = []
    for field, label in [("department", "Department"), ("function", "Function"), ("experienceLevel", "Level")]:
        value = (item.get(field) or {}).get("label")
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def scrape(company_name: str, company_id: str) -> list[Job]:
    """Ги симнува огласите на една компанија од SmartRecruiters и ги враќа како листа од Job."""
    jobs = []

    for page in range(MAX_PAGES):
        # Пауза пред секое барање освен првото.
        if page > 0:
            time.sleep(PAUSE_SECONDS)

        # offset кажува од кој оглас да почне страницата (0, 100, 200 ...).
        url = API_URL.format(company_id=quote(company_id), limit=PAGE_SIZE, offset=page * PAGE_SIZE)
        # fetch_html го враќа одговорот како текст, а json.loads го претвора во речник.
        data = json.loads(fetch_html(url))

        for item in data["content"]:
            # Идентификаторот на компанијата во линкот (на пр. "Endava").
            company_slug = (item.get("company") or {}).get("identifier") or company_id
            jobs.append(
                Job(
                    company=company_name,
                    title=item["name"],
                    location=_location(item),
                    url=JOB_PAGE_URL.format(company=quote(company_slug), job_id=item["id"]),
                    source="smartrecruiters",
                    description=_description(item),
                )
            )

        # Ако сме ги прочитале сите огласи (или страницата е празна), застануваме.
        if not data["content"] or len(jobs) >= data["totalFound"]:
            break
    else:
        # Овој дел се извршува само ако for-циклусот стигнал до MAX_PAGES без break.
        logger.warning(
            "smartrecruiters (%s): прочитани се најмногу %d страници, можеби има уште огласи.",
            company_name,
            MAX_PAGES,
        )

    # Ако нема ниту еден оглас, можеби компанијата навистина нема огласи,
    # но можеби и company_id е погрешен (API-то тогаш враќа празна листа, не грешка).
    if not jobs:
        logger.warning(
            "smartrecruiters (%s): пронајдени се 0 огласи. Провери го company_id „%s“.",
            company_name,
            company_id,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.smartrecruiters
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("Endava", "Endava")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
