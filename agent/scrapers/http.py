"""Shared HTTP helper for downloading HTML pages."""

import requests

TIMEOUT_SECONDS = 20

USER_AGENT = "InternshipAlertAgent/1.0 (personal student project)"


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to download {url}: status {response.status_code}"
        )

    return response.text
