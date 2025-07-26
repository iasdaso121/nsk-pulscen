import asyncio
import logging
import re
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


async def _fetch_with_session(
    session: aiohttp.ClientSession,
    url: str,
    *,
    allow_redirects: bool,
) -> Tuple[str, str]:
    async with session.get(url, allow_redirects=allow_redirects) as response:
        response.raise_for_status()
        html = await response.text()
        final_url = str(response.url)

    cookie = _solve_rbpcs_cookie(html)
    if cookie:
        from yarl import URL
        session.cookie_jar.update_cookies({"RBPCS": cookie}, response_url=URL(url))
        async with session.get(url, allow_redirects=allow_redirects) as response:
            response.raise_for_status()
            html = await response.text()
            final_url = str(response.url)

    lowered = html.lower()
    if any(pattern in lowered for pattern in BLOCK_PATTERNS):
        raise RuntimeError("Blocked or captcha detected")

    return html, final_url


async def fetch_html_with_retries(
    url: str,
    *,
    allow_redirects: bool = True,
    retries: int = 3,
) -> Tuple[str, str]:
    """Fetch a URL with retries and basic spam-block detection."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/116.0.0.0 Safari/537.36"
        )
    }

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
                logging.info("Fetching %s (attempt %s)", url, attempt)
                return await _fetch_with_session(
                    session, url, allow_redirects=allow_redirects
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
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

