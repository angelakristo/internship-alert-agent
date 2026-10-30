"""Sending email notifications about new relevant job postings."""

# html.escape ги претвора опасните знаци (<, >, & ...) во безбеден текст за HTML.
import html

# os.getenv ги чита променливите од околината (environment variables).
import os

# smtplib е вграден модул за праќање email преку SMTP сервер.
import smtplib

# EmailMessage ни помага да составиме email со наслов, текст и HTML.
from email.message import EmailMessage

# load_dotenv ги вчитува вредностите од .env фајлот во околината.
from dotenv import load_dotenv

from agent.models import Job

# Gmail SMTP сервер и порта за SSL (шифрирана) врска.
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

# Најмногу колку карактери од описот да прикажеме во email-от.
MAX_DESCRIPTION_LENGTH = 300

# Имиња на променливите што мора да постојат во .env.
REQUIRED_SETTINGS = ["EMAIL_SENDER", "EMAIL_APP_PASSWORD", "EMAIL_RECIPIENT"]


def _load_settings() -> dict[str, str]:
    """Ги вчитува поставките за email и проверува дали сите постојат."""
    # Ги вчитуваме вредностите од .env. Ако веќе постојат во околината
    # (на пр. на GitHub Actions), тие имаат предност.
    load_dotenv()

    settings = {}
    for name in REQUIRED_SETTINGS:
        value = os.getenv(name)
        # Ако вредноста ја нема или е празна, фрламе грешка со името (НЕ со вредноста).
        if not value:
            raise RuntimeError(
                f"Недостасува поставката {name}. Додај ја во .env фајлот."
            )
        settings[name] = value
    return settings


def _short_description(text: str) -> str:
    """Го скратува описот на најмногу MAX_DESCRIPTION_LENGTH карактери."""
    text = text.strip()
    if len(text) <= MAX_DESCRIPTION_LENGTH:
        return text
    # Сечеме и додаваме „…“ за да се гледа дека текстот продолжува.
    return text[: MAX_DESCRIPTION_LENGTH - 1].rstrip() + "…"


def _build_text_body(jobs: list[Job]) -> str:
    """Ја составува обичната текст верзија на email-от."""
    lines = [f"Пронајдени се {len(jobs)} нови огласи за пракса:", ""]
    for number, job in enumerate(jobs, start=1):
        lines.append(f"{number}. {job.title}")
        lines.append(f"   Компанија: {job.company}")
        lines.append(f"   Локација: {job.location or 'непозната'}")
        description = _short_description(job.description)
        if description:
            lines.append(f"   Опис: {description}")
        lines.append(f"   Аплицирај: {job.url}")
        lines.append("")
    return "\n".join(lines)


def _build_html_body(jobs: list[Job]) -> str:
    """Ја составува HTML верзијата на email-от (со кликабилни линкови)."""
    # Секој текст што доаѓа од туѓи страници го минуваме низ html.escape,
    # за да не може да внесе свој HTML или скрипта во нашиот email.
    cards = []
    for job in jobs:
        title = html.escape(job.title)
        company = html.escape(job.company)
        location = html.escape(job.location or "непозната")
        description = html.escape(_short_description(job.description))
        # quote=True ги заштитува и наводниците, бидејќи url-то оди во href="...".
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
                Аплицирај
              </a>
            </div>
            """
        )

    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;max-width:640px;margin:auto;">
        <h2>{len(jobs)} нови огласи за пракса</h2>
        {''.join(cards)}
      </body>
    </html>
    """


def send_job_alert(jobs: list[Job]) -> None:
    """Праќа еден email со сите дадени огласи. Ако нема огласи, не праќа ништо."""
    # Нема што да се прати.
    if not jobs:
        return

    settings = _load_settings()

    # Го составуваме email-от.
    message = EmailMessage()
    message["Subject"] = f"{len(jobs)} нови огласи за пракса"
    message["From"] = settings["EMAIL_SENDER"]
    message["To"] = settings["EMAIL_RECIPIENT"]

    # Прво обичен текст (за email програми што не прикажуваат HTML),
    # потоа HTML верзија како алтернатива.
    message.set_content(_build_text_body(jobs))
    message.add_alternative(_build_html_body(jobs), subtype="html")

    # Се поврзуваме со Gmail преку SSL, се најавуваме и го праќаме email-от.
    # "with" автоматски ја затвора врската на крајот.
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(settings["EMAIL_SENDER"], settings["EMAIL_APP_PASSWORD"])
        server.send_message(message)


# Тест: python -m agent.notifier  (праќа вистински email!)
if __name__ == "__main__":
    example_jobs = [
        Job(
            company="Example Corp",
            title="Software Engineering Intern",
            location="Skopje",
            url="https://example.com/careers/1",
            source="manual",
            description="Работа на backend сервиси во Python и учење од искусен тим.",
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
        print("Тест email-от е успешно испратен.")
    except Exception as error:
        # Ја печатиме грешката (таа никогаш не ја содржи лозинката).
        print(f"Испраќањето не успеа: {error}")
