import asyncio
import logging
import re
from playwright.async_api import async_playwright

from typing import Tuple

import aiohttp
from Crypto.Cipher import AES

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

def _solve_rbpcs_cookie(html: str) -> str | None:
    """Extract and decrypt RBPCS cookie from anti-bot page."""
    m = re.search(
        r'a=toNumbers\("([0-9a-f]+)"\).*?'
        r'b=toNumbers\("([0-9a-f]+)"\).*?'
        r'c=toNumbers\("([0-9a-f]+)"\)',
        html,
        re.I | re.S,
    )
    if not m:
        return None
    try:
        key, iv, data = (bytes.fromhex(x) for x in m.groups())
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.decrypt(data).hex()
    except Exception as exc:  # pragma: no cover - crypto errors unexpected
        logging.warning("Failed to decrypt RBPCS cookie: %s", exc)
        return None


async def _fetch_with_playwright(
    url: str,
    *,
    allow_redirects: bool = True,  # сейчас не используем, тк браузер сам делает редиректы
) -> Tuple[str, str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        response = await page.goto(url, wait_until="networkidle")

        html = await page.content()
        final_url = page.url

        lowered = html.lower()
        if any(pattern in lowered for pattern in BLOCK_PATTERNS):
            await browser.close()
            raise RuntimeError("Blocked or captcha detected")

        await browser.close()
        return html, final_url


async def fetch_html_with_retries(
    url: str,
    *,
    allow_redirects: bool = True,
    retries: int = 3,
) -> Tuple[str, str]:
    for attempt in range(1, retries + 1):
        try:
            logging.info("Fetching %s (attempt %s)", url, attempt)
            return await _fetch_with_playwright(url, allow_redirects=allow_redirects)
        except RuntimeError as exc:
            logging.warning(
                "Blocked or captcha detected on attempt %s/%s: %s",
                attempt,
                retries,
                exc,
            )
            if attempt == retries:
                raise
        except Exception as exc:
            logging.warning(
                "Error fetching %s on attempt %s/%s: %s",
                url,
                attempt,
                retries,
                exc,
            )
            if attempt == retries:
                raise
        await asyncio.sleep(2 * attempt)
