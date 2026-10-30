"""Scraper for Joberty (joberty.com) using its public JSON API."""

# json го претвора текстот од API-то во Python речници и листи.
import json

# logging служи за печатење пораки и предупредувања.
import logging

# time.sleep ни треба за пауза меѓу барањата.
import time

# urlencode ги составува параметрите за url (на пр. "location=North+Macedonia"),
# а quote ги кодира деловите од линкот до огласот.
from urllib.parse import quote, urlencode

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Јавниот API на Joberty што го користи и нивната веб страница.
API_URL = "https://backend.joberty.com/api/v1/jobs"

# Основа за линковите до огласите на веб страницата.
JOB_PAGE_URL = "https://www.joberty.com/job"

# Колку огласи да бараме по една страница од API-то.
PAGE_SIZE = 100

# Колку секунди да чекаме меѓу две барања, за да не го оптоваруваме сајтот.
PAUSE_SECONDS = 2

# Барањата што ги праќаме. Joberty има филтер за пракса (seniority) и за држава
# (location), па ги користиме нив наместо пребарување по зборови.
# Секое барање има и опис што го ставаме во Job.description.
SEARCHES = [
    # 1. Огласи означени како пракса во Македонија. Насловот често е само
    #    „Full Stack Developer“, па во описот запишуваме дека е пракса,
    #    за agent/filters.py да го препознае.
    ({"seniority": "Internship", "location": "North Macedonia"}, "Seniority: Internship"),
    # 2. Сите огласи во Македонија. Ова ги фаќа праксите што не се означени
    #    како Internship, но имаат „intern“ во насловот.
    ({"location": "North Macedonia"}, ""),
]


def _job_url(item: dict) -> str:
    """Го составува апсолутниот линк до огласот, исто како што го прави Joberty.

    Формат: https://www.joberty.com/job/<компанија>/<наслов-со-цртички>/<id>
    """
    # Насловот го претвораме во „slug“: без #, празните места и косите црти
    # стануваат цртички, а сè е со мали букви.
    slug = item["jobTitle"].replace("#", "").lower()
    for character in [" ", "/", "\\"]:
        slug = slug.replace(character, "-")
    # quote ги кодира необичните знаци (на пр. кирилица) за линкот да биде валиден.
    return f"{JOB_PAGE_URL}/{quote(item['companyUrlName'])}/{quote(slug)}/{item['id']}"


def _fetch_page(params: dict, page: int) -> dict:
    """Симнува една страница од API-то и ја враќа како Python речник."""
    query = urlencode({**params, "page": page, "pageSize": PAGE_SIZE})
    # fetch_html го враќа одговорот како текст, а json.loads го претвора во речник.
    return json.loads(fetch_html(f"{API_URL}?{query}"))


def scrape() -> list[Job]:
    """Ги симнува огласите од Joberty за Македонија и ги враќа како листа од Job."""
    jobs = []
    # Паметиме кои линкови веќе ги додадовме, за ист оглас да не се појави двапати
    # (на пр. оглас за пракса се наоѓа и во двете барања).
    seen_urls = set()
    # Бројач на барања, за да знаеме кога да паузираме.
    request_count = 0

    for params, description in SEARCHES:
        page = 0
        while True:
            # Пауза пред секое барање освен првото.
            if request_count > 0:
                time.sleep(PAUSE_SECONDS)
            request_count += 1

            data = _fetch_page(params, page)

            for item in data["items"]:
                url = _job_url(item)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                jobs.append(
                    Job(
                        company=item["companyName"],
                        title=item["jobTitle"],
                        # Градовите доаѓаат како листа, на пр. ["Skopje (North Macedonia)"].
                        location=", ".join(item.get("cities") or []),
                        url=url,
                        source="joberty",
                        description=description,
                    )
                )

            # API-то кажува колку страници има вкупно. Ако сме на последната, застануваме.
            page += 1
            if page >= data["totalPage"]:
                break

    # Ако нема ниту еден оглас, можеби навистина нема огласи во Македонија,
    # но можеби и API-то е сменето – вреди да се провери.
    if not jobs:
        logger.warning(
            "joberty: пронајдени се 0 огласи. Можеби нема огласи за Македонија, "
            "или API-то е сменето – провери го %s",
            API_URL,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.joberty
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape()
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
