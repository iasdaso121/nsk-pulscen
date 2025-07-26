import argparse
import asyncio
import json
import logging

from motor.motor_asyncio import AsyncIOMotorClient

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


async def gather_products(db, urls: list[str], concurrency: int = 10) -> list[dict]:
    """Parse product pages and store them in MongoDB."""
    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def parse_and_store(url: str) -> None:
        async with sem:
            try:
                product = await parse_product.parse(url)
                await db.products.insert_one(product)
                results.append(product)
                logging.info("Stored product %s", product.get("title"))
            except Exception as exc:
                logging.error("Failed to parse %s: %s", url, exc)

    await asyncio.gather(*(parse_and_store(u) for u in urls))
    return results


async def main(category_url: str, mongo_uri: str, out_file: str,
               link_concurrency: int = 5, product_concurrency: int = 10) -> None:
    client = AsyncIOMotorClient(mongo_uri)
    db = client.pulscen

    links = await gather_product_links(category_url, concurrency=link_concurrency)
    logging.info("Collected %s product links", len(links))

    products = await gather_products(db, links, concurrency=product_concurrency)
    with open(out_file, "w") as fh:
        json.dump(products, fh, ensure_ascii=False, indent=2)

    await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse all products from a Pulscen category")
    parser.add_argument("category_url", help="URL of the parent category")
    parser.add_argument("-o", "--out", default="products.json",
                        help="Path to output JSON file")
    parser.add_argument("-m", "--mongodb", default="mongodb://localhost:27017",
                        help="MongoDB connection URI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--link-concurrency", type=int, default=5,
                        help="Number of concurrent subcategory parsers")
    parser.add_argument("--product-concurrency", type=int, default=10,
                        help="Number of concurrent product fetchers")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s:%(message)s")

    asyncio.run(main(args.category_url, args.mongodb, args.out,
                     link_concurrency=args.link_concurrency,
                     product_concurrency=args.product_concurrency))
