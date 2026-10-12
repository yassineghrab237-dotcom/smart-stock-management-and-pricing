"""Conditions fournisseur et propositions converties en brouillons révisables."""

import json
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.repositories.stock_repo import product, remember
from services.stock_service.app.schemas.commerce_schemas import Mutation
from services.stock_service.app.schemas.product_schemas import normalize_price
from services.stock_service.app.services.replenishment import plan
from .crm import Id, contact, event, replay
from .purchases import order

router = APIRouter(prefix="/replenishment", tags=["Réapprovisionnement"])


class PolicyInput(Mutation):
    supplier_id: int = Field(ge=1, le=9223372036854775807)
    unit_cost_ht: str
    lead_days: int = Field(ge=1, le=365)
    min_quantity: int = Field(ge=1, le=1000000)
    pack_size: int = Field(ge=1, le=1000000)
    enabled: bool = True
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("unit_cost_ht")
    @classmethod
    def cost(cls, v):
        return normalize_price(v)


class DraftInput(Mutation):
    supplier_id: int = Field(ge=1, le=9223372036854775807)
    budget: str | None = None
    expected_fingerprint: str = Field(min_length=64, max_length=64)
    reference: str = Field(min_length=1, max_length=100)

    @field_validator("budget")
    @classmethod
    def money(cls, v):
        return normalize_price(v) if v is not None else None


@router.get("/policies/{product_id}")
def policy(product_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        product(db, product_id)
        row = db.execute(
            "SELECT * FROM replenishment_policies WHERE product_id=?", (product_id,)
        ).fetchone()
        return dict(
            policy=dict(row) if row else None,
            events=[
                dict(r)
                for r in db.execute(
                    "SELECT e.*,u.name actor_name FROM replenishment_events e JOIN users u ON u.id=e.actor_id WHERE product_id=? ORDER BY e.id DESC",
                    (product_id,),
                )
            ],
        )


@router.post("/policies/{product_id}")
def save_policy(
    product_id: Id, body: PolicyInput, request: Request, user=Depends(editor)
):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "replenishment-policy", product_id)
        if cached is not None:
            return cached
        product(db, product_id)
        supplier = contact(db, body.supplier_id)
        if supplier["kind"] == "CUSTOMER" or supplier["stage"] == "INACTIVE":
            raise HTTPException(422, "Fournisseur actif ou prospect requis.")
        previous = db.execute(
            "SELECT * FROM replenishment_policies WHERE product_id=?", (product_id,)
        ).fetchone()
        version = previous["version"] if previous else 0
        if version != body.expected_version:
            raise HTTPException(
                409, "Conditions modifiées ; actualisez avant de réessayer."
            )
        fields = body.model_dump(
            exclude={"idempotency_key", "expected_version", "reason"}
        )
        db.execute(
            "INSERT INTO replenishment_policies(product_id,supplier_id,unit_cost_ht,lead_days,min_quantity,pack_size,enabled,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET supplier_id=excluded.supplier_id,unit_cost_ht=excluded.unit_cost_ht,lead_days=excluded.lead_days,min_quantity=excluded.min_quantity,pack_size=excluded.pack_size,enabled=excluded.enabled,version=excluded.version,updated_at=excluded.updated_at",
            (
                product_id,
                body.supplier_id,
                body.unit_cost_ht,
                body.lead_days,
                body.min_quantity,
                body.pack_size,
                body.enabled,
                version + 1,
                now(),
            ),
        )
        audit = dict(
            reason=body.reason,
            before=dict(previous) if previous else None,
            after=fields,
        )
        db.execute(
            "INSERT INTO replenishment_events(product_id,detail,actor_id,created_at) VALUES (?,?,?,?)",
            (product_id, json.dumps(audit, ensure_ascii=False), user["id"], now()),
        )
        result = dict(
            db.execute(
                "SELECT * FROM replenishment_policies WHERE product_id=?", (product_id,)
            ).fetchone()
        )
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.get("/plan")
def get_plan(
    request: Request,
    supplier_id: int | None = Query(default=None, ge=1, le=9223372036854775807),
    budget: str | None = None,
    user=Depends(current_user),
):
    try:
        budget = normalize_price(budget) if budget is not None else None
    except ValueError:
        raise HTTPException(422, "Enveloppe HT invalide.")
    with connect(db_path(request)) as db:
        db.execute("BEGIN")
        return plan(db, supplier_id, budget)


@router.post("/draft", status_code=201)
def create_draft(body: DraftInput, request: Request, user=Depends(editor)):
    try:
        with connect(db_path(request), write=True) as db:
            cached, fingerprint = replay(db, body, user, "replenishment-draft")
            if cached is not None:
                return cached
            proposal = plan(db, body.supplier_id, body.budget)
            if proposal["fingerprint"] != body.expected_fingerprint:
                raise HTTPException(
                    409,
                    "Les stocks, conditions ou engagements ont changé. Actualisez la proposition.",
                )
            lines = [r for r in proposal["items"] if r["quantity"]]
            if not lines:
                raise HTTPException(
                    422,
                    "Aucune quantité à commander avec ces conditions et cette enveloppe.",
                )
            if len(lines) > 100:
                raise HTTPException(
                    422,
                    "Limitez à 100 produits par commande ; adaptez les conditions actives.",
                )
            cursor = db.execute(
                "INSERT INTO purchase_orders_local(reference,supplier_id,status,expected_on,note,created_at,actor_id) VALUES (?,?,'DRAFT',?,?,?,?)",
                (
                    body.reference,
                    body.supplier_id,
                    proposal["expected_on"],
                    "Proposition min/max validée localement ; coût et disponibilité fournisseur à reconfirmer.",
                    now(),
                    user["id"],
                ),
            )
            identity = cursor.lastrowid
            for r in lines:
                db.execute(
                    "INSERT INTO purchase_lines_local(order_id,product_id,sku,name,quantity,unit_cost_ht) VALUES (?,?,?,?,?,?)",
                    (
                        identity,
                        r["id"],
                        r["sku"],
                        r["name"],
                        r["quantity"],
                        r["unit_cost_ht"],
                    ),
                )
            event(
                db,
                body.supplier_id,
                "PURCHASE",
                f"Brouillon {body.reference} issu du réapprovisionnement",
                user["id"],
            )
            result = order(db, identity)
            remember(db, body.idempotency_key, user["id"], fingerprint, result)
            return result
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Référence de commande déjà utilisée.")
