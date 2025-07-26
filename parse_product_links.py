import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import List
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup


@dataclass
class ProductLink:
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


def parse_links(html: str, base_url: str) -> List[ProductLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[ProductLink] = []
    for container in soup.select('.product-listing__product-title a'):
        href = container.get("href")
        title = container.get_text(strip=True)
        if href:
            links.append(ProductLink(title=title, url=urljoin(base_url, href)))
    return links


def find_next_page(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    next_link = soup.select_one('a[rel="next"]')
    if next_link and next_link.get('href'):
        return urljoin(current_url, next_link['href'])
    return None


async def parse(url: str) -> List[dict]:
    page_url = url
    results: List[ProductLink] = []

    while page_url:
        html = await fetch_html(page_url)
        links = parse_links(html, url)
        logging.info("Found %s products on %s", len(links), page_url)
        results.extend(links)

        next_page = find_next_page(html, page_url)
        if next_page and next_page != page_url:
            page_url = next_page
        else:
            break

    return [asdict(link) for link in results]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse product links from a Pulscen subcategory page"
    )
    parser.add_argument("url", help="URL of the subcategory page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s:%(message)s")

    data = asyncio.run(parse(args.url))
    print(json.dumps(data, ensure_ascii=False, indent=2))
