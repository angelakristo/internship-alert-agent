"""Filtering of job postings by relevance and location."""

# re е вграден модул за регуларни изрази (пребарување шаблони во текст).
import re

from agent.models import Job

# ---------------------------------------------------------------------------
# Клучни зборови – менувај ги слободно овие листи.
# ---------------------------------------------------------------------------

# Почетоци на зборови што значат дека огласот е за пракса.
# Се фаќаат и изведените облици, на пр. "пракс" фаќа „пракса“, „праксата“, „пракси“.
INTERNSHIP_PREFIXES = [
    "пракс",
    "практикант",
    "стажант",
    "praktikant",
    "internship",
    "trainee",
    "ibornship",  # програмата за пракса на iBorn (на пр. „iBornship 2027“)
]

# Зборови за пракса што мора да се совпаднат ТОЧНО, како цел збор.
# "intern" не е префикс, инаку би ги фатил и "Internal" и "International".
INTERNSHIP_WHOLE_WORDS = [
    "intern",
    "interns",
]

# Области што не се IT и не нè интересираат (се проверува само насловот).
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

# Почетоци на македонски зборови за области што не се IT.
# Се фаќаат и изведените облици, на пр. "сметковод" фаќа „сметководство“, „сметководител“.
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

# Локации што ни одговараат. Доволно е локацијата да го СОДРЖИ зборот.
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

# Кратенки за локација што мора да се совпаднат само како ЦЕЛ збор,
# за на пр. "MK" да не се најде случајно во подолг збор.
LOCATION_WHOLE_WORDS = [
    "MK",
]


# ---------------------------------------------------------------------------
# Помошна функција
# ---------------------------------------------------------------------------


def _contains_whole_word(text: str, words: list[str]) -> bool:
    """True ако текстот содржи некој од зборовите како цел збор."""
    for word in words:
        # \b значи „граница на збор“: почеток/крај на текст, празно место,
        # интерпункција итн. Така "intern" НЕ се совпаѓа во "Internal".
        # re.escape ги заштитува специјалните знаци во зборот (ако ги има).
        pattern = r"\b" + re.escape(word) + r"\b"
        # re.IGNORECASE: не е важно дали буквите се големи или мали.
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _contains_word_prefix(text: str, prefixes: list[str]) -> bool:
    """True ако некој збор во текстот ПОЧНУВА со еден од дадените префикси."""
    for prefix in prefixes:
        # \b на почетокот: префиксот мора да е почеток на збор.
        # \w* потоа: по него може да следат било колку букви (или ниту една).
        pattern = r"\b" + re.escape(prefix) + r"\w*"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Филтри
# ---------------------------------------------------------------------------


def is_internship(job: Job) -> bool:
    """True ако насловот или описот укажува дека станува збор за пракса."""
    # Ги спојуваме насловот и описот за да ги провериме заедно.
    text = f"{job.title} {job.description}"
    # Пракса е ако има збор што почнува со некој префикс, ИЛИ точен збор "intern(s)".
    return _contains_word_prefix(text, INTERNSHIP_PREFIXES) or _contains_whole_word(
        text, INTERNSHIP_WHOLE_WORDS
    )


def is_excluded_field(job: Job) -> bool:
    """True ако насловот е за област што не е IT (маркетинг, продажба итн.)."""
    # Исфрлена е ако има цел англиски збор ИЛИ збор што почнува со македонски префикс.
    return _contains_whole_word(job.title, EXCLUDED_FIELD_WORDS) or _contains_word_prefix(
        job.title, EXCLUDED_FIELD_PREFIXES
    )


def is_location_ok(job: Job) -> bool:
    """True ако локацијата е непозната или е во Македонија / remote."""
    location = job.location.strip()

    # Ако локацијата е празна, не знаеме каде е – подобро да го покажеме огласот.
    if not location:
        return True

    # Кратенки како "MK" – само како цел збор.
    if _contains_whole_word(location, LOCATION_WHOLE_WORDS):
        return True

    # Останатите локации – доволно е да се содржат (без разлика на големи/мали букви).
    location_lower = location.lower()
    for word in LOCATION_WORDS:
        if word.lower() in location_lower:
            return True

    return False


def filter_relevant(jobs: list[Job]) -> list[Job]:
    """Ги враќа само огласите за пракса, во IT област, на прифатлива локација."""
    return [
        job
        for job in jobs
        if is_internship(job)
        and not is_excluded_field(job)
        and is_location_ok(job)
    ]


# Мал тест: python -m agent.filters
if __name__ == "__main__":
    # (наслов, локација) за секој пример оглас.
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

        # Ја наоѓаме причината зошто огласот (не) поминал.
        if not is_internship(job):
            result = "НЕ ПОМИНУВА – не е пракса"
        elif is_excluded_field(job):
            result = "НЕ ПОМИНУВА – не-IT област"
        elif not is_location_ok(job):
            result = "НЕ ПОМИНУВА – локација"
        else:
            result = "ПОМИНУВА"

        print(f"{title!r:32} | {location!r:18} | {result}")

    # Проверка дека filter_relevant го враќа истото (очекувано 6 огласи).
    all_jobs = [
        Job("Example Corp", t, loc, f"https://example.com/{t}", "manual")
        for t, loc in examples
    ]
    print(f"\nfilter_relevant врати {len(filter_relevant(all_jobs))} огласи (очекувано 6)")
