from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.schemas.stock_schemas import MovementInput
from services.stock_service.app.repositories.stock_repo import (
    MOVEMENT_SELECT,
    product,
    check_version,
    existing_request,
    remember,
)

router = APIRouter(prefix="/movements", tags=["Mouvements"])


@router.get("")
def movements(
    request: Request,
    product_id: Annotated[int | None, Query(ge=1, le=9223372036854775807)] = None,
    user=Depends(current_user),
):
    with connect(db_path(request)) as db:
        query = MOVEMENT_SELECT
        params = ()
        if product_id is not None:
            product(db, product_id)
            query += " WHERE m.product_id=?"
            params = (product_id,)
        return {
            "items": [
                dict(r) for r in db.execute(query + " ORDER BY m.id DESC", params)
            ]
        }


@router.post("", status_code=201)
def create(body: MovementInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        payload = {"operation": "movement", **body.model_dump()}
        cached, fingerprint = existing_request(
            db, body.idempotency_key, user["id"], payload
        )
        if cached is not None:
            return cached
        item = product(db, body.product_id)
        check_version(item, body.expected_version)
        before = item["current_stock"]
        if body.type != "ADJUSTMENT" and body.quantity <= 0:
            raise HTTPException(
                422, "La quantité d'entrée ou de sortie doit être positive."
            )
        after = (
            body.quantity
            if body.type == "ADJUSTMENT"
            else before + (body.quantity if body.type == "IN" else -body.quantity)
        )
        if after < 0:
            raise HTTPException(409, "Stock insuffisant pour cette sortie.")
        if after > 2147483647:
            raise HTTPException(422, "Stock maximum dépassé.")
        stamp = now()
        cursor = db.execute(
            "INSERT INTO movements(product_id,type,quantity,reason,stock_before,stock_after,created_at,actor_id) VALUES (?,?,?,?,?,?,?,?)",
            (
                body.product_id,
                body.type,
                body.quantity,
                body.reason,
                before,
                after,
                stamp,
                user["id"],
            ),
        )
        db.execute(
            "UPDATE products SET current_stock=?,version=version+1,updated_at=? WHERE id=?",
            (after, stamp, body.product_id),
        )
        result = dict(
            db.execute(
                MOVEMENT_SELECT + " WHERE m.id=?", (cursor.lastrowid,)
            ).fetchone()
        )
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
