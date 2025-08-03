import asyncio
import logging
import re
from playwright.async_api import async_playwright, Error

from typing import Tuple

from Crypto.Cipher import AES
from contextlib import contextmanager
import os
import tempfile
from errors import FetchError

# Substrings that may indicate the site blocked us.
# The generic word "captcha" was previously used but it also appears in
# legitimate page markup (e.g. "SmartCaptcha" footer) causing false
# positives. We now rely on more specific phrases likely present on a
# block page.
BLOCK_PATTERNS = [
    "не робот",
    "доступ ограничен",
    "слишком много запросов",
]

_playwright = None
_browser = None


async def get_browser():
    """Return a singleton Chromium browser instance."""
    global _playwright, _browser
    if _browser is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
    return _browser


async def close_browser():
    """Close the shared browser instance if it was created."""
    global _playwright, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None

async def _fetch_with_playwright(
    url: str,
    *,
    allow_redirects: bool = True,  # сейчас не используем, тк браузер сам делает редиректы
) -> Tuple[str, str]:
    browser = await get_browser()
    context = await browser.new_context()
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle")

        html = await page.content()
        final_url = page.url

        lowered = html.lower()
        if any(pattern in lowered for pattern in BLOCK_PATTERNS):
            raise RuntimeError("Blocked or captcha detected")

        return html, final_url
    finally:
        await context.close()


async def fetch_html_with_retries(
    url: str,
    *,
    allow_redirects: bool = True,
    retries: int = 3,
) -> Tuple[str, str]:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            logging.info("Fetching %s (attempt %s)", url, attempt)
            return await _fetch_with_playwright(url, allow_redirects=allow_redirects)
        except RuntimeError as exc:
            last_exc = exc
            logging.warning(
                "Blocked or captcha detected on attempt %s/%s: %s",
                attempt,
                retries,
                exc,
            )
        except Error as exc:
            last_exc = exc
            logging.warning(
                "Playwright error fetching %s on attempt %s/%s: %s",
                url,
                attempt,
                retries,
                exc,
            )
        except Exception as exc:
            last_exc = exc
            logging.warning(
                "Error fetching %s on attempt %s/%s: %s",
                url,
                attempt,
                retries,
                exc,
            )
        if attempt == retries:
            raise FetchError(f"Failed to fetch {url}") from last_exc
        await asyncio.sleep(2 * attempt)


@contextmanager
def atomic_writer(path: str):
    """Write to a temporary file and move it into place when done."""
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory)
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            yield fh
        os.replace(tmp_path, path)
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass
