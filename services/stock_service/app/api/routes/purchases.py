"""Commandes et réceptions fournisseurs atomiques, sans envoi externe."""

import sqlite3
from datetime import date
from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.schemas.commerce_schemas import Mutation, CancelInput
from services.stock_service.app.schemas.product_schemas import normalize_price
from services.stock_service.app.repositories.stock_repo import (
    product,
    check_version,
    remember,
)
from services.stock_service.app.services.commerce import amount, stock_change
from .crm import contact, event, replay

router = APIRouter(prefix="/purchases", tags=["Achats fournisseurs"])
Id = Annotated[int, Path(ge=1, le=9223372036854775807)]


class PurchaseLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    product_id: int = Field(ge=1, le=9223372036854775807)
    quantity: int = Field(ge=1, le=2147483647)
    unit_cost_ht: str

    @field_validator("unit_cost_ht")
    @classmethod
    def cost(cls, value):
        return normalize_price(value)


class PurchaseInput(Mutation):
    reference: str = Field(min_length=1, max_length=100)
    supplier_id: int = Field(ge=1, le=9223372036854775807)
    expected_on: str = Field(max_length=10)
    note: str = Field(default="", max_length=2000)
    lines: list[PurchaseLine] = Field(min_length=1, max_length=100)

    @field_validator("expected_on")
    @classmethod
    def day(cls, value):
        return date.fromisoformat(value).isoformat()

    @model_validator(mode="after")
    def distinct(self):
        if len({l.product_id for l in self.lines}) != len(self.lines):
            raise ValueError("Regroupez les lignes du même produit")
        return self


class Versioned(Mutation):
    expected_version: int = Field(ge=1)


class ReceiptLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    line_id: int = Field(ge=1, le=9223372036854775807)
    quantity: int = Field(ge=1, le=2147483647)
    expected_product_version: int = Field(ge=1)


class ReceiptInput(Versioned):
    reason: str = Field(min_length=1, max_length=1000)
    lines: list[ReceiptLine] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct(self):
        if len({l.line_id for l in self.lines}) != len(self.lines):
            raise ValueError("Lignes de réception dupliquées")
        return self


def order(db, identity):
    row = db.execute(
        "SELECT p.*,c.name supplier_name FROM purchase_orders_local p JOIN crm_contacts c ON c.id=p.supplier_id WHERE p.id=?",
        (identity,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Commande fournisseur introuvable.")
    result = dict(row)
    result["lines"] = [
        dict(r)
        for r in db.execute(
            "SELECT l.*,COALESCE((SELECT SUM(r.quantity) FROM purchase_receipts_local r WHERE r.line_id=l.id),0) received FROM purchase_lines_local l WHERE order_id=? ORDER BY id",
            (identity,),
        )
    ]
    result["receipts"] = [
        dict(r)
        for r in db.execute(
            "SELECT r.*,l.sku FROM purchase_receipts_local r JOIN purchase_lines_local l ON l.id=r.line_id WHERE l.order_id=? ORDER BY r.id DESC",
            (identity,),
        )
    ]
    result["total_ht"] = amount(
        sum(
            (Decimal(l["unit_cost_ht"]) * l["quantity"] for l in result["lines"]),
            Decimal(0),
        )
    )
    result["remaining_ht"] = amount(
        sum(
            (
                Decimal(l["unit_cost_ht"]) * (l["quantity"] - l["received"])
                for l in result["lines"]
            ),
            Decimal(0),
        )
    )
    return result


@router.get("/orders")
def orders(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT p.*,c.name supplier_name FROM purchase_orders_local p JOIN crm_contacts c ON c.id=p.supplier_id ORDER BY p.id DESC"
                )
            ]
        }


@router.get("/orders/{order_id}")
def detail(order_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        result = order(db, order_id)
        result["products"] = [
            product(db, line["product_id"]) for line in result["lines"]
        ]
        return result


@router.post("/orders", status_code=201)
def create(body: PurchaseInput, request: Request, user=Depends(editor)):
    try:
        with connect(db_path(request), write=True) as db:
            cached, fingerprint = replay(db, body, user, "purchase-create")
            if cached is not None:
                return cached
            supplier = contact(db, body.supplier_id)
            if supplier["kind"] == "CUSTOMER" or supplier["stage"] == "INACTIVE":
                raise HTTPException(422, "Un fournisseur non inactif est requis.")
            cursor = db.execute(
                "INSERT INTO purchase_orders_local(reference,supplier_id,status,expected_on,note,created_at,actor_id) VALUES (?,?,'DRAFT',?,?,?,?)",
                (
                    body.reference,
                    body.supplier_id,
                    body.expected_on,
                    body.note,
                    now(),
                    user["id"],
                ),
            )
            identity = cursor.lastrowid
            for line in body.lines:
                item = product(db, line.product_id)
                db.execute(
                    "INSERT INTO purchase_lines_local(order_id,product_id,sku,name,quantity,unit_cost_ht) VALUES (?,?,?,?,?,?)",
                    (
                        identity,
                        item["id"],
                        item["sku"],
                        item["name"],
                        line.quantity,
                        line.unit_cost_ht,
                    ),
                )
            event(
                db,
                body.supplier_id,
                "PURCHASE",
                f"Brouillon d'achat {body.reference} créé",
                user["id"],
            )
            result = order(db, identity)
            remember(db, body.idempotency_key, user["id"], fingerprint, result)
            return result
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Référence de commande déjà utilisée.")


@router.post("/orders/{order_id}/confirm")
def confirm(order_id: Id, body: Versioned, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "purchase-confirm", order_id)
        if cached is not None:
            return cached
        record = order(db, order_id)
        check_version(record, body.expected_version)
        if record["status"] != "DRAFT":
            raise HTTPException(409, "Seul un brouillon peut être confirmé.")
        db.execute(
            "UPDATE purchase_orders_local SET status='ORDERED',version=version+1,ordered_at=? WHERE id=?",
            (now(), order_id),
        )
        event(
            db,
            record["supplier_id"],
            "PURCHASE",
            f"Commande {record['reference']} confirmée localement, aucun envoi automatique",
            user["id"],
        )
        result = order(db, order_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/orders/{order_id}/receive")
def receive(order_id: Id, body: ReceiptInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "purchase-receive", order_id)
        if cached is not None:
            return cached
        record = order(db, order_id)
        check_version(record, body.expected_version)
        if record["status"] not in ("ORDERED", "PART_RECEIVED"):
            raise HTTPException(409, "Cette commande ne peut plus être réceptionnée.")
        for incoming in body.lines:
            line = next(
                (l for l in record["lines"] if l["id"] == incoming.line_id), None
            )
            if line is None or incoming.quantity > line["quantity"] - line["received"]:
                raise HTTPException(
                    409, "Ligne inconnue ou quantité supérieure au restant à recevoir."
                )
            stock_change(
                db,
                line["product_id"],
                incoming.quantity,
                user["id"],
                f"Réception {record['reference']} : {body.reason}",
                incoming.expected_product_version,
            )
            db.execute(
                "INSERT INTO purchase_receipts_local(line_id,quantity,reason,actor_id,created_at) VALUES (?,?,?,?,?)",
                (line["id"], incoming.quantity, body.reason, user["id"], now()),
            )
        updated = order(db, order_id)
        status = (
            "RECEIVED"
            if all(l["quantity"] == l["received"] for l in updated["lines"])
            else "PART_RECEIVED"
        )
        db.execute(
            "UPDATE purchase_orders_local SET status=?,version=version+1 WHERE id=?",
            (status, order_id),
        )
        event(
            db,
            record["supplier_id"],
            "RECEIPT",
            f"Réception de la commande {record['reference']} : {body.reason}",
            user["id"],
        )
        result = order(db, order_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: Id, body: CancelInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "purchase-cancel", order_id)
        if cached is not None:
            return cached
        record = order(db, order_id)
        check_version(record, body.expected_version)
        if record["status"] not in ("DRAFT", "ORDERED", "PART_RECEIVED"):
            raise HTTPException(409, "Commande déjà clôturée.")
        status = "CLOSED" if record["receipts"] else "CANCELLED"
        db.execute(
            "UPDATE purchase_orders_local SET status=?,version=version+1,note=note || ? WHERE id=?",
            (status, "\nSolde annulé : " + body.reason, order_id),
        )
        event(
            db,
            record["supplier_id"],
            "PURCHASE",
            f"Solde de {record['reference']} annulé : {body.reason}",
            user["id"],
        )
        result = order(db, order_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
