from dataclasses import dataclass
from typing import List, Optional

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
    supplier_url: Optional[str]
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
