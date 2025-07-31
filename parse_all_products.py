import argparse
import asyncio
import json
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager


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


async def gather_product_links(category_url: str, concurrency: int = 5) -> list[str]:
    """Collect product URLs from all subcategories of the given category."""
    subcats = await parse_categories.parse(category_url)
    logging.info("Found %s subcategories", len(subcats))

    sem = asyncio.Semaphore(concurrency)
    all_links: list[str] = []

    async def collect(sub: dict) -> None:
        url = sub["url"]
        async with sem:
            links = await parse_product_links.parse(url)
            all_links.extend(link["url"] for link in links)
            logging.info("%s links collected from %s", len(links), url)

    await asyncio.gather(*(collect(sc) for sc in subcats))
    return all_links


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
            except Exception as exc:  # noqa: BLE001
                logging.exception("Failed to parse %s: %s", url, exc)
                return

            try:
                await db.products.insert_one(product)
            except Exception as exc:  # noqa: BLE001
                logging.exception("Failed to store product %s: %s", url, exc)
                return

            data = json.dumps(product, ensure_ascii=False, default=str)
            async with write_lock:
                out_fh.write(data + "\n")
            logging.info("Stored product %s", product.get("title"))

    await asyncio.gather(*(parse_and_store(u) for u in urls))


async def main(category_url: str, mongo_uri: str, out_file: str,
               link_concurrency: int = 5, product_concurrency: int = 10,
               debug_dir: str | None = None) -> None:
    """Collect products from the given category and store them."""
    async with open_mongo(mongo_uri) as client:
        db = client.pulscen

        links = await gather_product_links(category_url, concurrency=link_concurrency)
        logging.info("Collected %s product links", len(links))

        with open(out_file, "w", encoding="utf-8") as fh:
            await gather_products(db, links, out_fh=fh, concurrency=product_concurrency, debug_dir=debug_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse all products from a Pulscen category")
    parser.add_argument("category_url", help="URL of the parent category")
    parser.add_argument("-o", "--out", default="products.jsonl",
                        help="Path to output JSONL file")
    parser.add_argument("-m", "--mongodb", default="mongodb://localhost:27017",
                        help="MongoDB connection URI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--link-concurrency", type=int, default=5,
                        help="Number of concurrent subcategory parsers")
    parser.add_argument("--product-concurrency", type=int, default=10,
                        help="Number of concurrent product fetchers")
    parser.add_argument("--debug-dir", help="Directory to save raw HTML samples")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s:%(message)s",
    )

    asyncio.run(main(args.category_url, args.mongodb, args.out,
                     link_concurrency=args.link_concurrency,
                     product_concurrency=args.product_concurrency,
                     debug_dir=args.debug_dir))
