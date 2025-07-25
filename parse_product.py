import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup


@dataclass
class PriceInfo:
    qnt: int
    discount: Optional[float]
    price: float


@dataclass
class SupplierOffer:
    price: List[PriceInfo]
    stock: Optional[str]
    delivery_time: Optional[str]
    package_info: Optional[str]
    purchase_url: Optional[str]


@dataclass
class Supplier:
    dealer_id: Optional[str]
    supplier_name: Optional[str]
    supplier_tel: Optional[str]
    supplier_address: Optional[str]
    supplier_description: Optional[str]
    supplier_offers: List[SupplierOffer]


@dataclass
class Attribute:
    attr_name: str
    attr_value: str


@dataclass
class Product:
    title: Optional[str]
    description: Optional[str]
    article: Optional[str]
    brand: Optional[str]
    country_of_origin: Optional[str]
    warranty_months: Optional[str]
    category: Optional[str]
    created_at: Optional[str]
    attributes: List[Attribute]
    suppliers: List[Supplier]


async def fetch_html(url: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            logging.info("Fetching %s", url)
            async with session.get(url) as response:
                response.raise_for_status()
                logging.info("Received HTTP %s", response.status)
                return await response.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logging.error("Network error while requesting %s: %s", url, exc)
        raise


def parse_attributes(soup: BeautifulSoup) -> List[Attribute]:
    result: List[Attribute] = []
    for row in soup.select("table tr"):
        cols = row.find_all("td")
        if len(cols) >= 2:
            name = cols[0].get_text(strip=True)
            value = cols[1].get_text(strip=True)
            if name:
                result.append(Attribute(attr_name=name, attr_value=value))
    return result


def parse_suppliers(soup: BeautifulSoup) -> List[Supplier]:
    suppliers: List[Supplier] = []
    for s in soup.select('.supplier'):
        dealer_id = s.get('data-dealer-id')
        name = s.select_one('.supplier__name')
        phone = s.select_one('.supplier__phone')
        address = s.select_one('.supplier__address')
        descr = s.select_one('.supplier__description')

        offers: List[SupplierOffer] = []
        for offer_block in s.select('.supplier__offer'):
            price_list: List[PriceInfo] = []
            for price_row in offer_block.select('.price-row'):
                qnt = price_row.get('data-quantity')
                price = price_row.get('data-price')
                disc = price_row.get('data-discount')
                if price:
                    price_list.append(
                        PriceInfo(
                            qnt=int(qnt) if qnt else 1,
                            discount=float(disc) if disc else None,
                            price=float(price),
                        )
                    )
            offers.append(
                SupplierOffer(
                    price=price_list,
                    stock=offer_block.get('data-stock'),
                    delivery_time=offer_block.get('data-delivery'),
                    package_info=offer_block.get('data-package'),
                    purchase_url=offer_block.get('data-purchase-url'),
                )
            )

        suppliers.append(
            Supplier(
                dealer_id=dealer_id,
                supplier_name=name.get_text(strip=True) if name else None,
                supplier_tel=phone.get_text(strip=True) if phone else None,
                supplier_address=address.get_text(strip=True) if address else None,
                supplier_description=descr.get_text(strip=True) if descr else None,
                supplier_offers=offers,
            )
        )
    return suppliers


def parse_product(html: str) -> Product:
    soup = BeautifulSoup(html, 'html.parser')

    title_tag = soup.select_one('h1')
    title = title_tag.get_text(strip=True) if title_tag else None

    descr_tag = soup.select_one('.product-description')
    description = descr_tag.get_text("\n", strip=True) if descr_tag else None

    article = None
    article_tag = soup.find(string=lambda x: x and 'Артикул' in x)
    if article_tag:
        parent = article_tag.parent
        if parent.name == 'td' and parent.find_next('td'):
            article = parent.find_next('td').get_text(strip=True)

    brand = None
    brand_tag = soup.find(string=lambda x: x and 'Бренд' in x)
    if brand_tag:
        parent = brand_tag.parent
        if parent.name == 'td' and parent.find_next('td'):
            brand = parent.find_next('td').get_text(strip=True)

    country = None
    country_tag = soup.find(string=lambda x: x and 'Страна происхождения' in x)
    if country_tag:
        parent = country_tag.parent
        if parent.name == 'td' and parent.find_next('td'):
            country = parent.find_next('td').get_text(strip=True)

    warranty = None
    w_tag = soup.find(string=lambda x: x and 'Гарантийный срок' in x)
    if w_tag:
        parent = w_tag.parent
        if parent.name == 'td' and parent.find_next('td'):
            warranty = parent.find_next('td').get_text(strip=True)

    category = None
    cat_tag = soup.select_one('.breadcrumbs li:last-child')
    if cat_tag:
        category = cat_tag.get_text(strip=True)

    created_at = None
    created_tag = soup.find(string=lambda x: x and 'размещено' in x.lower())
    if created_tag:
        created_at = created_tag.strip().split()[-2] + ' ' + created_tag.strip().split()[-1]

    attributes = parse_attributes(soup)
    suppliers = parse_suppliers(soup)

    return Product(
        title=title,
        description=description,
        article=article,
        brand=brand,
        country_of_origin=country,
        warranty_months=warranty,
        category=category,
        created_at=created_at,
        attributes=attributes,
        suppliers=suppliers,
    )


async def parse(url: str) -> dict:
    html = await fetch_html(url)
    product = parse_product(html)
    logging.info("Parsed product: %s", product.title)
    return asdict(product)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Parse a product page from nsk.pulscen.ru')
    parser.add_argument('url', help='URL of the product page')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format='%(levelname)s:%(message)s')

    data = asyncio.run(parse(args.url))
    print(json.dumps(data, ensure_ascii=False, indent=2))
