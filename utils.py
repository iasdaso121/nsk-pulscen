import asyncio
import logging
from typing import Tuple

import aiohttp

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

async def fetch_html_with_retries(url: str, *, allow_redirects: bool = True, retries: int = 3) -> Tuple[str, str]:
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
                async with session.get(url, allow_redirects=allow_redirects) as response:
                    response.raise_for_status()
                    html = await response.text()
                    final_url = str(response.url)
                    lowered = html.lower()
                    if any(pattern in lowered for pattern in BLOCK_PATTERNS):
                        raise RuntimeError("Blocked or captcha detected")
                    return html, final_url
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
            logging.warning("Error fetching %s on attempt %s/%s: %s", url, attempt, retries, exc)
            if attempt == retries:
                raise
            await asyncio.sleep(2 * attempt)

