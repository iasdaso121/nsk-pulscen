import asyncio
import logging
import re
from typing import Tuple

import httpx
from Crypto.Cipher import AES
from fake_useragent import UserAgent

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
    session: httpx.AsyncClient,
    url: str,
    *,
    allow_redirects: bool,
) -> Tuple[str, str]:
    response = await session.get(url, follow_redirects=allow_redirects)
    response.raise_for_status()
    html = response.text
    final_url = str(response.url)

    cookie = _solve_rbpcs_cookie(html)
    if cookie:
        session.cookies.set("RBPCS", cookie)
        response = await session.get(url, follow_redirects=allow_redirects)
        response.raise_for_status()
        html = response.text
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
    ua = UserAgent()

    headers = {
        "User-Agent": ua.random,
    }

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(headers=headers, trust_env=True) as session:
                logging.info("Fetching %s (attempt %s)", url, attempt)
                return await _fetch_with_session(
                    session, url, allow_redirects=allow_redirects
                )
        except (httpx.HTTPError, asyncio.TimeoutError, RuntimeError) as exc:
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

