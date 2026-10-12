"""Campagnes de comptage et validation atomique des écarts de stock."""

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, model_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.repositories.stock_repo import (
    product,
    check_version,
    remember,
)
from .crm import Id, Mutation, replay

router = APIRouter(prefix="/inventories", tags=["Inventaires physiques"])


class InventoryInput(Mutation):
    title: str = Field(min_length=1, max_length=180)
    product_ids: list[int] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def ids(self):
        if len(set(self.product_ids)) != len(self.product_ids) or any(
            p < 1 or p > 9223372036854775807 for p in self.product_ids
        ):
            raise ValueError("Produits distincts et identifiants valides requis")
        return self


class CountInput(Mutation):
    quantity: int = Field(ge=0, le=2147483647)
    expected_version: int = Field(ge=1)
    expected_product_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class CloseInput(Mutation):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


def detail(db, identity):
    row = db.execute(
        "SELECT * FROM inventory_sessions WHERE id=?", (identity,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Campagne introuvable.")
    return {
        **dict(row),
        "lines": [
            dict(r)
            for r in db.execute(
                "SELECT l.*,p.sku,p.name,p.current_stock,p.version current_product_version FROM inventory_lines l JOIN products p ON p.id=l.product_id WHERE l.session_id=? ORDER BY p.name,l.id",
                (identity,),
            )
        ],
        "events": [
            dict(r)
            for r in db.execute(
                "SELECT e.*,u.name actor_name FROM inventory_events e JOIN users u ON u.id=e.actor_id WHERE session_id=? ORDER BY e.id DESC",
                (identity,),
            )
        ],
    }


def log(db, identity, info, actor):
    db.execute(
        "INSERT INTO inventory_events(session_id,detail,actor_id,created_at) VALUES (?,?,?,?)",
        (identity, json.dumps(info, ensure_ascii=False), actor, now()),
    )


@router.get("")
def listing(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT s.*,(SELECT COUNT(*) FROM inventory_lines l WHERE l.session_id=s.id) line_count FROM inventory_sessions s ORDER BY s.id DESC"
                )
            ]
        }


@router.get("/{inventory_id}")
def get(inventory_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        db.execute("BEGIN")
        return detail(db, inventory_id)


@router.post("", status_code=201)
def create(body: InventoryInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "inventory-create")
        if cached is not None:
            return cached
        cursor = db.execute(
            "INSERT INTO inventory_sessions(title,status,created_at,actor_id) VALUES (?,'OPEN',?,?)",
            (body.title, now(), user["id"]),
        )
        identity = cursor.lastrowid
        for pid in body.product_ids:
            p = product(db, pid)
            db.execute(
                "INSERT INTO inventory_lines(session_id,product_id,expected_stock,product_version) VALUES (?,?,?,?)",
                (identity, pid, p["current_stock"], p["version"]),
            )
        log(
            db,
            identity,
            {"action": "Ouverture", "produits": len(body.product_ids)},
            user["id"],
        )
        result = detail(db, identity)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/{inventory_id}/lines/{line_id}/count")
def count(
    inventory_id: Id,
    line_id: Id,
    body: CountInput,
    request: Request,
    user=Depends(editor),
):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "inventory-count", line_id)
        if cached is not None:
            if cached["id"] != inventory_id:
                raise HTTPException(409, "Clé associée à une autre campagne.")
            return cached
        campaign = detail(db, inventory_id)
        if campaign["status"] != "OPEN":
            raise HTTPException(409, "Campagne clôturée.")
        line = next((l for l in campaign["lines"] if l["id"] == line_id), None)
        if line is None:
            raise HTTPException(404, "Ligne introuvable dans cette campagne.")
        if line["version"] != body.expected_version:
            raise HTTPException(409, "Comptage modifié. Actualisez la campagne.")
        p = product(db, line["product_id"])
        check_version(p, body.expected_product_version)
        db.execute(
            "UPDATE inventory_lines SET counted=?,expected_stock=?,product_version=?,version=version+1 WHERE id=?",
            (body.quantity, p["current_stock"], p["version"], line_id),
        )
        db.execute(
            "UPDATE inventory_sessions SET version=version+1 WHERE id=?",
            (inventory_id,),
        )
        log(
            db,
            inventory_id,
            {
                "action": "Comptage",
                "sku": p["sku"],
                "avant": line["counted"],
                "compté": body.quantity,
                "stock_théorique": p["current_stock"],
                "motif": body.reason,
            },
            user["id"],
        )
        result = detail(db, inventory_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/{inventory_id}/{action}")
def close(
    inventory_id: Id,
    action: str,
    body: CloseInput,
    request: Request,
    user=Depends(editor),
):
    if action not in ("apply", "cancel"):
        raise HTTPException(404, "Action inconnue.")
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(
            db, body, user, "inventory-" + action, inventory_id
        )
        if cached is not None:
            return cached
        record = detail(db, inventory_id)
        if record["status"] != "OPEN" or record["version"] != body.expected_version:
            raise HTTPException(409, "Campagne modifiée ou clôturée. Actualisez-la.")
        stamp = now()
        if action == "apply":
            if any(l["counted"] is None for l in record["lines"]):
                raise HTTPException(
                    422, "Chaque produit doit être compté avant validation."
                )
            for l in record["lines"]:
                if l["product_version"] != l["current_product_version"]:
                    raise HTTPException(
                        409,
                        f"Produit {l['sku']} modifié après comptage : actualisez et recomptez cette ligne.",
                    )
                if l["counted"] != l["current_stock"]:
                    db.execute(
                        "INSERT INTO movements(product_id,type,quantity,reason,stock_before,stock_after,created_at,actor_id) VALUES (?,'ADJUSTMENT',?,?,?,?,?,?)",
                        (
                            l["product_id"],
                            l["counted"],
                            f"Inventaire #{inventory_id} {record['title']} : {body.reason}",
                            l["current_stock"],
                            l["counted"],
                            stamp,
                            user["id"],
                        ),
                    )
                    db.execute(
                        "UPDATE products SET current_stock=?,version=version+1,updated_at=? WHERE id=?",
                        (l["counted"], stamp, l["product_id"]),
                    )
        db.execute(
            "UPDATE inventory_sessions SET status=?,version=version+1,closed_at=? WHERE id=?",
            ("APPLIED" if action == "apply" else "CANCELLED", stamp, inventory_id),
        )
        log(
            db,
            inventory_id,
            {
                "action": (
                    "Écarts appliqués" if action == "apply" else "Campagne annulée"
                ),
                "motif": body.reason,
            },
            user["id"],
        )
        result = detail(db, inventory_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
