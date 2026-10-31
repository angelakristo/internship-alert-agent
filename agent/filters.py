"""Filtering of job postings by relevance and location."""

import re

from agent.models import Job


INTERNSHIP_PREFIXES = [
    "пракс",
    "практикант",
    "стажант",
    "praktikant",
    "internship",
    "trainee",
    "ibornship",
]

INTERNSHIP_WHOLE_WORDS = [
    "intern",
    "interns",
]

EXCLUDED_FIELD_WORDS = [
    "marketing",
    "sales",
    "hr",
    "human resources",
    "recruiter",
    "finance",
    "accounting",
    "legal",
    "event",
    "office",
]

EXCLUDED_FIELD_PREFIXES = [
    "маркетинг",
    "продажб",
    "продаж",
    "сметковод",
    "финанси",
    "книговод",
    "правн",
    "право",
    "администрати",
    "човечки ресурси",
    "регрутаци",
    "продавач",
    "комерцијал",
]

LOCATION_WORDS = [
    "North Macedonia",
    "Macedonia",
    "Skopje",
    "Скопје",
    "Македонија",
    "Bitola",
    "Битола",
    "Ohrid",
    "Охрид",
    "remote",
]

LOCATION_WHOLE_WORDS = [
    "MK",
]


def _contains_whole_word(text: str, words: list[str]) -> bool:
    for word in words:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _contains_word_prefix(text: str, prefixes: list[str]) -> bool:
    for prefix in prefixes:
        pattern = r"\b" + re.escape(prefix) + r"\w*"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def is_internship(job: Job) -> bool:
    text = f"{job.title} {job.description}"
    return _contains_word_prefix(text, INTERNSHIP_PREFIXES) or _contains_whole_word(
        text, INTERNSHIP_WHOLE_WORDS
    )


def is_excluded_field(job: Job) -> bool:
    return _contains_whole_word(job.title, EXCLUDED_FIELD_WORDS) or _contains_word_prefix(
        job.title, EXCLUDED_FIELD_PREFIXES
    )


def is_location_ok(job: Job) -> bool:
    location = job.location.strip()

    if not location:
        return True

    if _contains_whole_word(location, LOCATION_WHOLE_WORDS):
        return True

    location_lower = location.lower()
    for word in LOCATION_WORDS:
        if word.lower() in location_lower:
            return True

    return False


def filter_relevant(jobs: list[Job]) -> list[Job]:
    return [
        job
        for job in jobs
        if is_internship(job)
        and not is_excluded_field(job)
        and is_location_ok(job)
    ]


if __name__ == "__main__":
    examples = [
        ("Software Engineering Intern", "MK"),
        ("Data Science Internship", "Remote"),
        ("Internship Program 2027", ""),
        ("Internal Tools Engineer", "MK"),
        ("Marketing Intern", "MK"),
        ("Java Intern", "DE"),
        ("Backend Intern", "Hybrid, Berlin"),
        ("Пријави за праксата 2027", "MK"),
        ("Praktikantin Softwareentwicklung", "Remote"),
        ("Пракса во сметководство", "MK"),
        ("iBornship 2027 – Frontend", "Skopje"),
    ]

    for title, location in examples:
        job = Job(
            company="Example Corp",
            title=title,
            location=location,
            url=f"https://example.com/{title}",
            source="manual",
        )

        if not is_internship(job):
            result = "REJECTED – not an internship"
        elif is_excluded_field(job):
            result = "REJECTED – non-IT field"
        elif not is_location_ok(job):
            result = "REJECTED – location"
        else:
            result = "ACCEPTED"

        print(f"{title!r:32} | {location!r:18} | {result}")

    all_jobs = [
        Job("Example Corp", t, loc, f"https://example.com/{t}", "manual")
        for t, loc in examples
    ]
    print(f"\nfilter_relevant returned {len(filter_relevant(all_jobs))} jobs (expected 6)")
