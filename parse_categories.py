import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import fetch_html_with_retries


@dataclass
class Subcategory:
    title: str
    url: str


async def fetch_html(url: str) -> str:
    html, _ = await fetch_html_with_retries(url)
    return html


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
