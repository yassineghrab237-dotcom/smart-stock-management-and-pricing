import sqlite3
from typing import Annotated
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Path
from pydantic import ValidationError
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.schemas.product_schemas import (
    ProductInput,
    ProductPatch,
    PriceChange,
)
from services.stock_service.app.repositories.stock_repo import (
    product,
    check_version,
    existing_request,
    remember,
)

router = APIRouter(prefix="/products", tags=["Produits"])
ProductId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.get("")
def products(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r) for r in db.execute("SELECT * FROM products ORDER BY name,id")
            ]
        }


@router.get("/{product_id}")
def get_product(product_id: ProductId, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return product(db, product_id)


@router.post("", status_code=201)
def create(body: ProductInput, request: Request, user=Depends(editor)):
    fields = body.model_dump()
    stamp = now()
    try:
        with connect(db_path(request), write=True) as db:
            columns = list(fields) + ["created_at", "updated_at"]
            values = list(fields.values()) + [stamp, stamp]
            cursor = db.execute(
                f"INSERT INTO products({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                values,
            )
            return product(db, cursor.lastrowid)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Ce SKU est déjà utilisé.")


@router.patch("/{product_id}")
def update(
    product_id: ProductId, body: ProductPatch, request: Request, user=Depends(editor)
):
    try:
        with connect(db_path(request), write=True) as db:
            old = product(db, product_id)
            check_version(old, body.expected_version)
            fields = body.model_dump(exclude_unset=True, exclude={"expected_version"})
            merged = {key: old[key] for key in ProductInput.model_fields}
            merged.update(fields)
            try:
                validated = ProductInput.model_validate(merged).model_dump()
            except ValidationError:
                raise HTTPException(422, "Métadonnées, prix ou seuils invalides.")
            if not fields:
                raise HTTPException(422, "Aucune modification fournie.")
            fields = {key: validated[key] for key in fields}
            assignments = ",".join(f"{key}=?" for key in fields)
            db.execute(
                f"UPDATE products SET {assignments},version=version+1,updated_at=? WHERE id=?",
                [*fields.values(), now(), product_id],
            )
            return product(db, product_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Ce SKU est déjà utilisé.")


@router.patch("/{product_id}/price")
def change_price(
    product_id: ProductId, body: PriceChange, request: Request, user=Depends(editor)
):
    with connect(db_path(request), write=True) as db:
        payload = {"operation": "price", "product_id": product_id, **body.model_dump()}
        cached, fingerprint = existing_request(
            db, body.idempotency_key, user["id"], payload
        )
        if cached is not None:
            return cached
        old = product(db, product_id)
        check_version(old, body.expected_version)
        if old["min_price"] is not None and Decimal(body.price) < Decimal(
            old["min_price"]
        ):
            raise HTTPException(422, "Le prix proposé est inférieur au prix minimum.")
        stamp = now()
        db.execute(
            "INSERT INTO price_history(product_id,old_price,new_price,reason,actor_id,created_at) VALUES (?,?,?,?,?,?)",
            (
                product_id,
                old["current_price"],
                body.price,
                body.reason,
                user["id"],
                stamp,
            ),
        )
        db.execute(
            "UPDATE products SET current_price=?,version=version+1,updated_at=? WHERE id=?",
            (body.price, stamp, product_id),
        )
        result = product(db, product_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.get("/{product_id}/prices")
def prices(product_id: ProductId, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        product(db, product_id)
        rows = db.execute(
            "SELECT h.id,h.old_price,h.new_price,h.reason,u.name actor_name,h.created_at FROM price_history h JOIN users u ON u.id=h.actor_id WHERE h.product_id=? ORDER BY h.id DESC",
            (product_id,),
        )
        return {"items": [dict(r) for r in rows]}
