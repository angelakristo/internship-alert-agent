"""Data model for a job posting (Job)."""

import hashlib
from dataclasses import dataclass


@dataclass
class Job:
    company: str
    title: str
    location: str
    url: str
    source: str

    description: str = ""

    @property
    def job_id(self) -> str:
        url_bytes = self.url.encode("utf-8")
        full_hash = hashlib.sha256(url_bytes).hexdigest()
        return full_hash[:16]


if __name__ == "__main__":
    example_job = Job(
        company="Example Corp",
        title="Software Engineering Intern",
        location="Skopje",
        url="https://example.com/careers/123",
        source="manual",
    )

    print(example_job)
    print("job_id:", example_job.job_id)
