"""Generic scraper for companies that use the Ashby ATS (public Job Board API)."""

# json го претвора текстот од API-то во Python речници и листи.
import json

# logging служи за печатење пораки и предупредувања.
import logging

# quote го кодира името на job board-от (на пр. "IT Labs" → "IT%20Labs").
from urllib.parse import quote

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Јавниот Ashby Job Board API. Ги враќа сите огласи одеднаш, без страничење.
API_URL = "https://api.ashbyhq.com/posting-api/job-board/{job_board_name}"


def _location(item: dict) -> str:
    """Ги спојува главната и дополнителните локации, плус „(Remote)“ ако е далечинска работа."""
    # Главната локација (на пр. "Miami") и дополнителните (на пр. "Boston", "Skopje").
    # Ги земаме сите, бидејќи Скопје може да е и меѓу дополнителните.
    names = [item.get("location")]
    names += [extra.get("location") for extra in item.get("secondaryLocations") or []]
    text = ", ".join(name for name in names if name)
    if item.get("isRemote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _description(item: dict) -> str:
    """Краток опис: оддел, тим и тип на вработување.

    Типот на вработување е важен: кога е „Intern“, agent/filters.py препознава
    пракса дури и ако насловот не го содржи тој збор.
    """
    parts = []
    for field, label in [("department", "Department"), ("team", "Team"), ("employmentType", "Employment")]:
        value = item.get(field)
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def scrape(company_name: str, job_board_name: str) -> list[Job]:
    """Ги симнува огласите на една компанија од Ashby и ги враќа како листа од Job."""
    # 1. Го симнуваме JSON-от од API-то. fetch_html го враќа како текст,
    #    а json.loads го претвора во речник.
    url = API_URL.format(job_board_name=quote(job_board_name))
    data = json.loads(fetch_html(url))

    # 2. Секој оглас од листата "jobs" го претвораме во Job.
    jobs = []
    for item in data["jobs"]:
        # Огласите што не се јавно објавени ги прескокнуваме.
        if item.get("isListed") is False:
            continue
        jobs.append(
            Job(
                company=company_name,
                title=item["title"],
                location=_location(item),
                # jobUrl е веќе целосен линк до јавната страница на огласот.
                url=item["jobUrl"],
                source="ashby",
                description=_description(item),
            )
        )

    # Ако нема ниту еден оглас, можеби компанијата навистина нема огласи,
    # но можеби и job_board_name е погрешен.
    if not jobs:
        logger.warning(
            "ashby (%s): пронајдени се 0 огласи. Провери го job_board_name „%s“.",
            company_name,
            job_board_name,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.ashby
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("IT Labs", "IT Labs")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
