"""Generic scraper for companies that use the Teamtailor ATS (public jobs.json feed)."""

# json го претвора текстот од feed-от во Python речници и листи.
import json

# logging служи за печатење пораки и предупредувања.
import logging

# time.sleep ни треба за пауза меѓу барањата.
import time

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Секоја Teamtailor career страница има јавен JSON feed на /jobs.json.
# Страниците се читаат со ?page=1, ?page=2 ... додека не дојде празна страница.
FEED_URL = "https://{career_domain}/jobs.json?page={page}"

# Најмногу колку страници да прочитаме.
MAX_PAGES = 10

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме сајтот.
PAUSE_SECONDS = 2


def _location(posting: dict) -> str:
    """Ги спојува сите локации од огласот, плус „(Remote)“ ако е далечинска работа."""
    places = []
    for place in posting.get("jobLocation") or []:
        address = place.get("address") or {}
        # Град и регион/држава, на пр. "Skopje, North Macedonia".
        parts = [address.get("addressLocality"), address.get("addressRegion") or address.get("addressCountry")]
        text = ", ".join(part.strip() for part in parts if part and part.strip())
        if text:
            places.append(text)
    location = "; ".join(places)

    # Според schema.org стандардот, далечинска работа е означена со TELECOMMUTE.
    if posting.get("jobLocationType") == "TELECOMMUTE":
        location = f"{location} (Remote)" if location else "Remote"
    return location


def _description(posting: dict) -> str:
    """Краток опис: тип на вработување (на пр. FULL_TIME или INTERN).

    Feed-от нема податок за оддел, па го земаме само типот на вработување.
    Кога е „INTERN“, agent/filters.py препознава пракса дури и ако насловот
    не го содржи тој збор.
    """
    employment = posting.get("employmentType")
    # employmentType може да биде еден текст или листа од повеќе типови.
    if isinstance(employment, list):
        employment = ", ".join(employment)
    return f"Employment: {employment}" if employment else ""


def scrape(company_name: str, career_domain: str) -> list[Job]:
    """Ги симнува огласите на една компанија од Teamtailor и ги враќа како листа од Job."""
    # Дозволуваме доменот да е запишан и со "https://" и со "/" на крајот.
    domain = career_domain.removeprefix("https://").removeprefix("http://").rstrip("/")

    jobs = []
    # Паметиме кои линкови веќе ги додадовме, за да застанеме ако сајтот
    # ја игнорира страницата и постојано ги враќа истите огласи.
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):
        # Пауза пред секое барање освен првото.
        if page > 1:
            time.sleep(PAUSE_SECONDS)

        # fetch_html го враќа одговорот како текст, а json.loads го претвора во речник.
        data = json.loads(fetch_html(FEED_URL.format(career_domain=domain, page=page)))

        new_on_page = 0
        for item in data.get("items") or []:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            new_on_page += 1

            # _jobposting ги содржи деталите на огласот (локација, тип на вработување).
            posting = item.get("_jobposting") or {}
            jobs.append(
                Job(
                    company=company_name,
                    title=item["title"],
                    location=_location(posting),
                    url=url,
                    source="teamtailor",
                    description=_description(posting),
                )
            )

        # Празна страница (или само огласи што веќе ги имаме) значи дека сме стигнале до крајот.
        if new_on_page == 0:
            break

    # Ако нема ниту еден оглас, можеби компанијата навистина нема огласи,
    # но можеби и доменот е погрешен.
    if not jobs:
        logger.warning(
            "teamtailor (%s): пронајдени се 0 огласи. Провери го career_domain „%s“.",
            company_name,
            career_domain,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.teamtailor
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("Nion", "career.nionit.com")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
