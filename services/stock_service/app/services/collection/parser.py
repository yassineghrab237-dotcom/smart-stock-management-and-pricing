"""Extraction de valeurs structurées ; aucune description longue ni image copiée."""

import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from services.stock_service.app.schemas.product_schemas import normalize_price
from .network import CollectionError


class StructuredPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None
        self.props = {}
        self.h1 = []
        self.in_h1 = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.current = []
        if tag == "h1":
            self.in_h1 = True
        key = attrs.get("itemprop")
        value = attrs.get("content") or attrs.get("href")
        if key and value:
            self.props.setdefault(key, []).append(value)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)
        if self.in_h1:
            self.h1.append(data)


def text(value, limit=200):
    return value.strip()[:limit] if isinstance(value, str) else ""


def extract(raw, url):
    html = StructuredPage()
    try:
        html.feed(raw.decode("utf-8", errors="replace"))
    except (ValueError, RecursionError):
        raise CollectionError("Page HTML illisible.")
    products = []
    for script in html.scripts:
        try:
            data = json.loads(script)
        except (ValueError, RecursionError):
            continue
        queue = [data]
        visited = 0
        while queue and visited < 50000:
            item = queue.pop()
            visited += 1
            if isinstance(item, list):
                queue.extend(item)
            elif isinstance(item, dict):
                kind = item.get("@type", [])
                if kind == "Product" or isinstance(kind, list) and "Product" in kind:
                    products.append(item)
                queue.extend(v for v in item.values() if isinstance(v, (dict, list)))
    if len(products) > 1:
        matching = [
            p
            for p in products
            if urlsplit(text(p.get("url"), 2000)).path == urlsplit(url).path
        ]
        if len(matching) != 1:
            raise CollectionError(
                "Plusieurs produits structurés : rapprochement ambigu."
            )
        products = matching
    if products:
        p = products[0]
        offers = p.get("offers")
        offers = offers if isinstance(offers, list) else [offers]
        if not offers or any(not isinstance(o, dict) for o in offers):
            raise CollectionError("Aucune offre structurée exploitable.")
        values = {
            (
                str(o.get("price", "")),
                str(o.get("priceCurrency", "")),
                str(o.get("availability", "")),
            )
            for o in offers
        }
        if len(values) != 1:
            raise CollectionError(
                "Plusieurs offres différentes ; variante à contrôler manuellement."
            )
        offer = offers[0]
        brand = p.get("brand")
        spec = offer.get("priceSpecification", {})
        result = dict(
            name=text(p.get("name")),
            brand=text(brand.get("name") if isinstance(brand, dict) else brand),
            manufacturer_ref=text(p.get("mpn"), 160),
            merchant_sku=text(p.get("sku"), 160),
            gtin=text(
                p.get("gtin13") or p.get("gtin14") or p.get("gtin") or p.get("gtin8"),
                20,
            ),
            price=str(offer.get("price", "")),
            currency=text(offer.get("priceCurrency")),
            availability=text(offer.get("availability")),
            tax_basis=(
                "TTC"
                if isinstance(spec, dict) and spec.get("valueAddedTaxIncluded") is True
                else (
                    "HT"
                    if isinstance(spec, dict)
                    and spec.get("valueAddedTaxIncluded") is False
                    else "UNKNOWN"
                )
            ),
        )
    else:

        def unique(key):
            values = set(html.props.get(key, []))
            if len(values) > 1:
                raise CollectionError("Métadonnées produit ambiguës.")
            return next(iter(values), "")

        result = dict(
            name=text(" ".join(html.h1)),
            brand="",
            manufacturer_ref=text(unique("mpn"), 160),
            merchant_sku=text(unique("sku"), 160),
            gtin="",
            price=unique("price"),
            currency=unique("priceCurrency"),
            availability=unique("availability"),
            tax_basis="UNKNOWN",
        )
    try:
        result["price"] = normalize_price(result["price"])
    except ValueError:
        raise CollectionError("Prix structuré absent ou invalide.")
    if result["currency"] not in ("TND", "EUR", "USD"):
        raise CollectionError("Devise absente ou non prise en charge.")
    state = result["availability"].rstrip("/").rsplit("/", 1)[-1]
    result["availability"] = {
        "InStock": "IN_STOCK",
        "OutOfStock": "OUT_OF_STOCK",
        "SoldOut": "OUT_OF_STOCK",
    }.get(state, "UNKNOWN")
    gtin = result["gtin"]
    if gtin and (
        len(gtin) not in (8, 12, 13, 14)
        or not gtin.isascii()
        or not gtin.isdigit()
        or sum(int(n) * (3 if i % 2 == 0 else 1) for i, n in enumerate(gtin[-2::-1]))
        % 10
        != (-int(gtin[-1])) % 10
    ):
        result["gtin"] = ""
    if not result["name"]:
        raise CollectionError("Nom du produit absent.")
    return result
