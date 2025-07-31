import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import fetch_html_with_retries


@dataclass
class ProductLink:
    title: str
    url: str


async def fetch_html(url: str) -> tuple[str, str]:
    return await fetch_html_with_retries(url, allow_redirects=True)


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
    """Parse product links from a subcategory page."""

    page_num = 1
    results: List[ProductLink] = []

    while True:
        page_url = url if page_num == 1 else f"{url}?page={page_num}"
        html, final_url = await fetch_html(page_url)

        # If we requested a page beyond the last one, the server will redirect
        # to the base URL without the pagination parameter. In this case we
        # stop without parsing the duplicated first page.
        if page_num > 1 and "?page=" not in final_url:
            break

        links = parse_links(html, url)
        logging.info("Found %s products on %s", len(links), final_url)
        if not links:
            logging.info("No products found, stopping at %s", final_url)
            break
        results.extend(links)

        page_num += 1

    return [asdict(link) for link in results]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse product links from a Pulscen subcategory page"
    )
    parser.add_argument("url", help="URL of the subcategory page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s:%(message)s",
    )

    data = asyncio.run(parse(args.url))
    print(json.dumps(data, ensure_ascii=False, indent=2))
