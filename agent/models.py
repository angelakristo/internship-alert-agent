"""Data model for a job posting (Job)."""

# hashlib ни дава функции за хаширање (на пр. sha256).
import hashlib

# dataclass автоматски ги прави __init__, __repr__ и __eq__ за нас,
# па не мораме сами да ги пишуваме.
from dataclasses import dataclass


@dataclass
class Job:
    """Еден оглас за пракса пронајден на Careers страница."""

    # Задолжителни полиња: мора да се зададат при креирање на Job.
    company: str   # Име на компанијата (на пр. "Google")
    title: str     # Наслов на огласот (на пр. "Software Engineering Intern")
    location: str  # Локација (на пр. "Skopje" или "Remote")
    url: str       # Линк до огласот
    source: str    # Од каде е земен огласот (на пр. "greenhouse", "lever")

    # Опционално поле: ако не се зададе, ќе биде празен стринг.
    # Полињата со default вредност мора да бидат ПОСЛЕ задолжителните,
    # инаку Python ќе фрли грешка. Затоа description е последно.
    description: str = ""

    @property
    def job_id(self) -> str:
        """Стабилен уникатен ID на огласот, добиен од неговото url."""
        # 1. Го претвораме url-то во бајти, бидејќи sha256 работи со бајти.
        url_bytes = self.url.encode("utf-8")
        # 2. Го пресметуваме sha256 hash-от и го добиваме како hex стринг.
        full_hash = hashlib.sha256(url_bytes).hexdigest()
        # 3. Ги земаме само првите 16 карактери – доволно кратко, а сепак уникатно.
        #    Истото url секогаш дава ист ID, па така знаеме дали огласот е веќе виден.
        return full_hash[:16]


if __name__ == "__main__":
    example_job = Job(
        company="Example Corp",
        title="Software Engineering Intern",
        location="Skopje",
        url="https://example.com/careers/123",
        source="manual",
    )

    # Го печатиме огласот и неговиот ID.
    print(example_job)
    print("job_id:", example_job.job_id)
