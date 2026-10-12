"""Relevés manuels traçables. Aucun accès réseau ou changement de prix."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Annotated
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Request, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.schemas.product_schemas import normalize_price
from services.stock_service.app.repositories.stock_repo import (
    product,
    existing_request,
    remember,
)

router = APIRouter(prefix="/market", tags=["Veille concurrentielle"])
DOMAINS = {
    "Tunisianet": "tunisianet.com.tn",
    "Mytek": "mytek.tn",
    "Spacenet": "spacenet.tn",
}


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    product_id: int = Field(ge=1, le=9223372036854775807)
    retailer: Literal["Tunisianet", "Mytek", "Spacenet"]
    source_url: str = Field(max_length=2000)
    manufacturer_ref: str = Field(min_length=1, max_length=160)
    variant: str = Field(min_length=1, max_length=400)
    price: str
    currency: Literal["TND", "EUR", "USD"]
    tax_basis: Literal["TTC", "HT", "UNKNOWN"]
    delivery: str | None = None
    availability: Literal["IN_STOCK", "OUT_OF_STOCK", "UNKNOWN"]
    confirmed: bool = False
    note: str = Field(min_length=1, max_length=1000)
    observed_at: str = Field(max_length=60)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("price", "delivery")
    @classmethod
    def money(cls, value):
        return normalize_price(value) if value is not None else None

    @field_validator("manufacturer_ref", "variant", "note")
    @classmethod
    def text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Champ requis")
        return value

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
            raise ValueError("Date avec fuseau requise, non future")
        return stamp.astimezone(timezone.utc).isoformat()

    @model_validator(mode="after")
    def source(self):
        url = urlsplit(self.source_url)
        domain = DOMAINS[self.retailer]
        if (
            url.scheme != "https"
            or url.hostname not in (domain, "www." + domain)
            or url.username
            or url.password
            or url.port not in (None, 443)
            or url.path in ("", "/")
        ):
            raise ValueError("URL HTTPS de fiche produit de l'enseigne requise")
        self.source_url = urlunsplit(("https", domain, url.path, url.query, ""))
        return self


@router.post("/observations", status_code=201)
def add(body: Observation, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        payload = {"operation": "market-observation", **body.model_dump()}
        cached, fingerprint = existing_request(
            db, body.idempotency_key, user["id"], payload
        )
        if cached is not None:
            return cached
        product(db, body.product_id)
        fields = body.model_dump(exclude={"idempotency_key"})
        fields.update(created_at=now(), actor_id=user["id"])
        cursor = db.execute(
            f"INSERT INTO market_observations({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            list(fields.values()),
        )
        result = {"id": cursor.lastrowid}
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.get("/products/{product_id}")
def read(
    product_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    request: Request,
    user=Depends(current_user),
):
    with connect(db_path(request)) as db:
        item = product(db, product_id)
        # Rank in SQL before limiting history: old records never become current again.
        rows = db.execute(
            """
            SELECT * FROM (
              SELECT o.*, u.name actor_name,
                ROW_NUMBER() OVER(PARTITION BY o.source_url ORDER BY o.observed_at DESC,o.id DESC) ranking
              FROM market_observations o JOIN users u ON u.id=o.actor_id WHERE product_id=?
            ) ORDER BY observed_at DESC,id DESC LIMIT 500
        """,
            (product_id,),
        ).fetchall()
    groups = {}
    observations = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for row in rows:
        entry = dict(row)
        entry["confirmed"] = bool(entry["confirmed"])
        entry["stale"] = datetime.fromisoformat(entry["observed_at"]) < cutoff
        entry["current"] = entry.pop("ranking") == 1
        entry["delta_to_lowest"] = None
        entry["total"] = None
        entry["eligible"] = (
            entry["current"]
            and not entry["stale"]
            and entry["confirmed"]
            and entry["availability"] == "IN_STOCK"
            and entry["tax_basis"] != "UNKNOWN"
            and entry["delivery"] is not None
        )
        if entry["eligible"]:
            entry["total"] = format(
                Decimal(entry["price"]) + Decimal(entry["delivery"]), ".4f"
            )
            key = (
                entry["currency"],
                entry["tax_basis"],
                entry["manufacturer_ref"].casefold(),
                entry["variant"].casefold(),
            )
            groups.setdefault(key, []).append(entry)
        observations.append(entry)
    for entries in groups.values():
        if len({e["retailer"] for e in entries}) < 2:
            continue
        minimum = min(Decimal(e["total"]) for e in entries)
        for entry in entries:
            entry["delta_to_lowest"] = format(Decimal(entry["total"]) - minimum, ".4f")
    return {"product": item, "items": observations, "freshness_hours": 24}
