"""Sending email notifications about new relevant job postings."""

import html
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

from agent.models import Job

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

MAX_DESCRIPTION_LENGTH = 300

REQUIRED_SETTINGS = ["EMAIL_SENDER", "EMAIL_APP_PASSWORD", "EMAIL_RECIPIENT"]


def _load_settings() -> dict[str, str]:
    load_dotenv()

    settings = {}
    for name in REQUIRED_SETTINGS:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(
                f"Missing setting {name}. Add it to the .env file."
            )
        settings[name] = value
    return settings


def _short_description(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_DESCRIPTION_LENGTH:
        return text
    return text[: MAX_DESCRIPTION_LENGTH - 1].rstrip() + "…"


def _build_text_body(jobs: list[Job]) -> str:
    lines = [f"Found {len(jobs)} new internship postings:", ""]
    for number, job in enumerate(jobs, start=1):
        lines.append(f"{number}. {job.title}")
        lines.append(f"   Company: {job.company}")
        lines.append(f"   Location: {job.location or 'unknown'}")
        description = _short_description(job.description)
        if description:
            lines.append(f"   Description: {description}")
        lines.append(f"   Apply: {job.url}")
        lines.append("")
    return "\n".join(lines)


def _build_html_body(jobs: list[Job]) -> str:
    cards = []
    for job in jobs:
        title = html.escape(job.title)
        company = html.escape(job.company)
        location = html.escape(job.location or "unknown")
        description = html.escape(_short_description(job.description))
        url = html.escape(job.url, quote=True)

        description_html = (
            f'<p style="margin:8px 0;color:#444;">{description}</p>' if description else ""
        )
        cards.append(
            f"""
            <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px;">
              <h3 style="margin:0 0 4px 0;">{title}</h3>
              <p style="margin:0;color:#555;"><b>{company}</b> · {location}</p>
              {description_html}
              <a href="{url}" style="display:inline-block;margin-top:8px;padding:8px 14px;
                 background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;">
                Apply
              </a>
            </div>
            """
        )

    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;max-width:640px;margin:auto;">
        <h2>{len(jobs)} new internship postings</h2>
        {''.join(cards)}
      </body>
    </html>
    """


def send_job_alert(jobs: list[Job]) -> None:
    if not jobs:
        return

    settings = _load_settings()

    message = EmailMessage()
    message["Subject"] = f"{len(jobs)} new internship postings"
    message["From"] = settings["EMAIL_SENDER"]
    message["To"] = settings["EMAIL_RECIPIENT"]

    message.set_content(_build_text_body(jobs))
    message.add_alternative(_build_html_body(jobs), subtype="html")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(settings["EMAIL_SENDER"], settings["EMAIL_APP_PASSWORD"])
        server.send_message(message)


if __name__ == "__main__":
    example_jobs = [
        Job(
            company="Example Corp",
            title="Software Engineering Intern",
            location="Skopje",
            url="https://example.com/careers/1",
            source="manual",
            description="Work on backend services in Python and learn from an experienced team.",
        ),
        Job(
            company="Example Labs",
            title="Data Science Internship",
            location="Remote",
            url="https://example.com/careers/2",
            source="manual",
        ),
    ]

    try:
        send_job_alert(example_jobs)
        print("Test email sent successfully.")
    except Exception as error:
        print(f"Sending failed: {error}")
