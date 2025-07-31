import argparse
import asyncio
import json
import logging
from typing import Iterable

from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from pymongo.errors import PyMongoError


@asynccontextmanager
async def open_mongo(uri: str):
    """Async context manager for AsyncIOMotorClient."""
    client = AsyncIOMotorClient(uri)
    try:
        yield client
    finally:
        client.close()

import parse_categories
import parse_product_links
import parse_product
from utils import atomic_writer
from errors import FetchError, ParseError


async def gather_product_links(category_url: str) -> list[str]:
    """Collect product URLs from all subcategories of the given category."""
    subcats = await parse_categories.parse(category_url)
    logging.info("Found %s subcategories", len(subcats))

    links: list[str] = []
    for sub in subcats:
        url = sub["url"]
        sub_links = await parse_product_links.parse(url)
        logging.info("%s links collected from %s", len(sub_links), url)
        links.extend(link["url"] for link in sub_links)

    return links


async def gather_products(db, urls: list[str], out_fh, concurrency: int = 10, debug_dir: str | None = None) -> None:
    """Parse product pages and store them in MongoDB and JSONL file on the fly."""
    sem = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    html_saved = False

    async def parse_and_store(url: str) -> None:
        nonlocal html_saved
        async with sem:
            debug_path = None
            if debug_dir and not html_saved:
                import os
                os.makedirs(debug_dir, exist_ok=True)
                debug_path = os.path.join(debug_dir, "sample.html")
                html_saved = True

            try:
                product = await parse_product.parse(url, debug_html_path=debug_path)
            except FetchError as exc:
                logging.error("Network error for %s: %s", url, exc)
                return
            except ParseError as exc:
                logging.warning("Parse error for %s: %s", url, exc)
                return

            try:
                await db.products.update_one(
                    {"_id": product["url"]},
                    {"$set": product},
                    upsert=True,
                )
            except PyMongoError as exc:
                logging.exception("Database error for %s: %s", url, exc)
                return

            data = json.dumps(product, ensure_ascii=False, default=str)
            async with write_lock:
                out_fh.write(data + "\n")
            logging.info("Stored product %s", product.get("title"))

    await asyncio.gather(*(parse_and_store(u) for u in urls))


async def main(category_url: str, mongo_uri: str, out_file: str,
               product_concurrency: int = 10, debug_dir: str | None = None) -> None:
    """Collect products from the given category and store them."""
    async with open_mongo(mongo_uri) as client:
        db = client.pulscen

        links = await gather_product_links(category_url)
        logging.info("Collected %s product links", len(links))

        with atomic_writer(out_file) as fh:
            await gather_products(db, links, out_fh=fh, concurrency=product_concurrency, debug_dir=debug_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse all products from a Pulscen category")
    parser.add_argument("category_url", help="URL of the parent category")
    parser.add_argument("-o", "--out", default="products.jsonl",
                        help="Path to output JSONL file")
    parser.add_argument("-m", "--mongodb", default="mongodb://localhost:27017",
                        help="MongoDB connection URI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--product-concurrency", type=int, default=10,
                        help="Number of concurrent product fetchers")
    parser.add_argument("--debug-dir", help="Directory to save raw HTML samples")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s:%(message)s",
    )

    asyncio.run(
        main(
            args.category_url,
            args.mongodb,
            args.out,
            product_concurrency=args.product_concurrency,
            debug_dir=args.debug_dir,
        )
    )
