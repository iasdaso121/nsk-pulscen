import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import List
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup


@dataclass
class Subcategory:
    title: str
    url: str


async def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/116.0.0.0 Safari/537.36"
        )
    }
    async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
        logging.info("Fetching %s", url)
        async with session.get(url) as response:
            response.raise_for_status()
            logging.info("Received HTTP %s", response.status)
            return await response.text()


def parse_subcategories(html: str, base_url: str) -> List[Subcategory]:
    soup = BeautifulSoup(html, "html.parser")
    subs: List[Subcategory] = []
    for a in soup.select("a.rblb-link"):
        href = a.get("href")
        title = a.get_text(strip=True)
        if href and title:
            subs.append(Subcategory(title=title, url=urljoin(base_url, href)))
    return subs


async def parse(url: str) -> List[dict]:
    html = await fetch_html(url)
    subcats = parse_subcategories(html, url)
    logging.info("Found %s subcategories", len(subcats))
    return [asdict(sc) for sc in subcats]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse subcategories from a Pulscen category page"
    )
    parser.add_argument("url", help="URL of the category page")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(message)s",
    )

    data = asyncio.run(parse(args.url))
    print(json.dumps(data, ensure_ascii=False, indent=2))
