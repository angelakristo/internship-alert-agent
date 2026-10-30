"""Shared HTTP helper for downloading HTML pages."""

# requests е библиотека за праќање HTTP барања (симнување веб страници).
import requests

# Колку секунди чекаме одговор пред да се откажеме.
TIMEOUT_SECONDS = 20

# User-Agent му кажува на серверот кој ја бара страницата.
# Чесно се претставуваме наместо да се преправаме дека сме прелистувач.
USER_AGENT = "InternshipAlertAgent/1.0 (personal student project)"


def fetch_html(url: str) -> str:
    """Ја симнува страницата на дадениот url и го враќа HTML-от како текст."""
    # Го праќаме барањето со нашиот User-Agent и со timeout.
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )

    # Ако серверот не врати 200 (OK), фрламе грешка со јасна порака.
    if response.status_code != 200:
        raise RuntimeError(
            f"Неуспешно симнување на {url}: статус {response.status_code}"
        )

    # Го враќаме HTML-от како обичен текст.
    return response.text
