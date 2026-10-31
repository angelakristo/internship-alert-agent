"""Generic scraper for career pages that publish schema.org JobPosting data (JSON-LD)."""

# json го чита JSON текстот од <script type="application/ld+json"> блоковите.
import json

# logging служи за печатење пораки и предупредувања.
import logging

# re (регуларни изрази) ни треба за да препознаеме линкови до огласи.
import re

# time.sleep ни треба за пауза меѓу барањата.
import time

# urljoin прави апсолутни линкови, а urlsplit го дели линкот на делови (домен, патека...).
from urllib.parse import urljoin, urlsplit

# BeautifulSoup ни помага да го пребаруваме HTML-от.
from bs4 import BeautifulSoup

from agent.models import Job
from agent.scrapers.http import fetch_html

# Logger со името на овој модул, за да знаеме од каде доаѓа пораката.
logger = logging.getLogger(__name__)

# Ако листата нема JSON-LD, најмногу колку поединечни огласи да отвориме.
MAX_DETAIL_PAGES = 30

# Пауза меѓу отворањето на поединечните огласи (во секунди).
PAUSE_SECONDS = 1

# Најмногу колку карактери од описот да зачуваме.
MAX_DESCRIPTION_LENGTH = 500

# Зборови во патеката на линкот што укажуваат дека тоа е страница на оглас,
# на пр. "/jobs/java-developer" или "/careers/positions/123".
JOB_LINK_PATTERN = re.compile(r"/(jobs?|careers?|positions?|vacanc(y|ies)|openings?|oglas\w*)/", re.IGNORECASE)


def _plain_text(html: str) -> str:
    """Го претвора HTML-от во обичен текст: без тагови, без ентитети, без вишок празни места."""
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return " ".join(text.split())


def _is_job_posting(data: dict) -> bool:
    """True ако објектот е од тип JobPosting (@type може да е текст или листа)."""
    kind = data.get("@type")
    if isinstance(kind, list):
        return "JobPosting" in kind
    return kind == "JobPosting"


def _find_job_postings(data) -> list[dict]:
    """Ги бара сите JobPosting објекти, каде и да се во JSON-от.

    JSON-LD може да е еден објект, листа, да има "@graph", или огласите да се
    вгнездени длабоко (на пр. WebPage → ItemList → ListItem → JobPosting).
    Затоа го поминуваме целиот JSON рекурзивно (функцијата се повикува самата себе).
    """
    found = []
    if isinstance(data, list):
        for element in data:
            found.extend(_find_job_postings(element))
    elif isinstance(data, dict):
        if _is_job_posting(data):
            found.append(data)
        else:
            for value in data.values():
                found.extend(_find_job_postings(value))
    return found


def _job_postings_from_html(html: str) -> list[dict]:
    """Ги чита сите JSON-LD блокови од страницата и ги враќа JobPosting објектите."""
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text())
        except json.JSONDecodeError:
            # Некои сајтови имаат неисправен JSON-LD – само го прескокнуваме.
            continue
        postings.extend(_find_job_postings(data))
    return postings


def _location(posting: dict) -> str:
    """Ја составува локацијата од jobLocation: град и држава, плус „(Remote)“."""
    places = posting.get("jobLocation") or []
    # jobLocation може да е еден објект или листа од објекти.
    if isinstance(places, dict):
        places = [places]

    parts = []
    for place in places:
        address = place.get("address") if isinstance(place, dict) else None
        if isinstance(address, str):
            # Понекогаш адресата е само текст, на пр. "Skopje, North Macedonia".
            parts.append(address.strip())
        elif isinstance(address, dict):
            country = address.get("addressCountry")
            # Државата може да е објект, на пр. {"name": "MK"}.
            if isinstance(country, dict):
                country = country.get("name")
            text = ", ".join(str(part).strip() for part in [address.get("addressLocality"), country] if part)
            if text:
                parts.append(text)
    location = "; ".join(parts)

    # Според schema.org стандардот, далечинска работа е означена со TELECOMMUTE.
    if posting.get("jobLocationType") == "TELECOMMUTE":
        location = f"{location} (Remote)" if location else "Remote"
    return location


def _description(posting: dict) -> str:
    """Опис без HTML. Ако описот го нема, го земаме барем типот на вработување.

    Типот на вработување е важен: кога е „INTERN“, agent/filters.py препознава пракса.
    """
    text = _plain_text(str(posting.get("description") or ""))
    if not text:
        employment = posting.get("employmentType")
        if isinstance(employment, list):
            employment = ", ".join(employment)
        text = f"Employment: {employment}" if employment else ""
    return text[:MAX_DESCRIPTION_LENGTH]


def _job_links(html: str, careers_url: str) -> list[str]:
    """Ги наоѓа линковите до поединечни огласи на истиот сајт (најмногу MAX_DETAIL_PAGES)."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlsplit(careers_url).netloc
    links = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(careers_url, anchor["href"]).split("#")[0]
        # Само линкови на истиот домен, што личат на оглас, и не се самата листа.
        if urlsplit(url).netloc != host or url.rstrip("/") == careers_url.rstrip("/"):
            continue
        if JOB_LINK_PATTERN.search(urlsplit(url).path + "/") and url not in links:
            links.append(url)
    return links[:MAX_DETAIL_PAGES]


def scrape(company_name: str, careers_url: str) -> list[Job]:
    """Ги чита огласите (JSON-LD JobPosting) од careers страницата и ги враќа како листа од Job."""
    # 1. Ја симнуваме careers страницата и бараме JobPosting во неа.
    html = fetch_html(careers_url)
    # Секој пронајден оглас го чуваме заедно со страницата од која е прочитан
    # (за релативните линкови и за огласите што немаат свое "url").
    found = [(posting, careers_url) for posting in _job_postings_from_html(html)]

    # 2. Ако листата нема JSON-LD, ги отвораме поединечните огласи.
    if not found:
        for index, link in enumerate(_job_links(html, careers_url)):
            if index > 0:
                time.sleep(PAUSE_SECONDS)
            try:
                page_html = fetch_html(link)
            except Exception:
                # Ако еден оглас не може да се отвори, продолжуваме со другите.
                logger.warning("jsonld (%s): не можам да го отворам %s", company_name, link)
                continue
            found.extend((posting, link) for posting in _job_postings_from_html(page_html))

    # 3. Секој JobPosting го претвораме во Job, без дупликати.
    jobs = []
    seen_urls = set()
    for posting, page_url in found:
        title = _plain_text(str(posting.get("title") or ""))
        if not title:
            continue
        # Ако огласот нема свое "url", ја користиме страницата каде го најдовме.
        url = urljoin(page_url, str(posting.get("url") or page_url))
        # Клучот е линк + наслов, бидејќи повеќе огласи може да се на иста страница.
        if (url, title) in seen_urls:
            continue
        seen_urls.add((url, title))

        jobs.append(
            Job(
                company=company_name,
                title=title,
                location=_location(posting),
                url=url,
                source="jsonld",
                description=_description(posting),
            )
        )

    # Ако нема ниту еден оглас, можеби страницата е сменета или нема JSON-LD.
    if not jobs:
        logger.warning(
            "jsonld (%s): пронајдени се 0 огласи. Провери дали %s сè уште има JobPosting податоци.",
            company_name,
            careers_url,
        )

    return jobs


# Се извршува само кога го стартуваме фајлот директно:
# python -m agent.scrapers.jsonld
if __name__ == "__main__":
    # Вклучуваме logging за да се гледаат предупредувањата.
    logging.basicConfig(level=logging.INFO)

    found_jobs = scrape("vector8", "https://www.vector8.com/en/careers")
    for job in found_jobs:
        print(f"- {job.title} | {job.company} | {job.location} | {job.description} | {job.url}")
    print(f"Вкупно огласи: {len(found_jobs)}")
