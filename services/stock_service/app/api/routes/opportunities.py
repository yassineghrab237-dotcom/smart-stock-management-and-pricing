"""Pipeline commercial : intentions séparées du chiffre d'affaires confirmé."""

import json
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.schemas.product_schemas import normalize_price
from services.stock_service.app.repositories.stock_repo import remember
from .crm import Mutation, Id, contact, event, replay

router = APIRouter(prefix="/crm", tags=["Opportunités commerciales"])


class Opportunity(Mutation):
    title: str = Field(min_length=1, max_length=180)
    stage: Literal["NEW", "QUALIFIED", "PROPOSAL", "WON", "LOST"] = "NEW"
    expected_ttc: str | None = None
    close_on: str = Field(max_length=10)
    quote_id: int | None = Field(default=None, ge=1, le=9223372036854775807)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("expected_ttc")
    @classmethod
    def amount(cls, v):
        return normalize_price(v) if v is not None else None

    @field_validator("close_on")
    @classmethod
    def day(cls, v):
        return date.fromisoformat(v).isoformat()


class UpdateOpportunity(Opportunity):
    expected_version: int = Field(ge=1)


def validate(db, body, contact_id):
    c = contact(db, contact_id)
    if c["kind"] == "SUPPLIER" or c["stage"] == "INACTIVE":
        raise HTTPException(422, "Client actif ou prospect requis.")
    if body.quote_id is not None:
        q = db.execute(
            "SELECT kind,customer_id,status FROM commercial_documents WHERE id=?",
            (body.quote_id,),
        ).fetchone()
        if (
            not q
            or q["kind"] != "QUOTE"
            or q["customer_id"] != contact_id
            or q["status"] == "CANCELLED"
        ):
            raise HTTPException(
                422, "Le devis doit appartenir à ce client et ne pas être annulé."
            )


@router.get("/contacts/{contact_id}/opportunities")
def listing(contact_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        contact(db, contact_id)
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT o.*,d.reference quote_reference FROM crm_opportunities o LEFT JOIN commercial_documents d ON d.id=o.quote_id WHERE o.contact_id=? ORDER BY o.id DESC",
                    (contact_id,),
                )
            ]
        }


@router.post("/contacts/{contact_id}/opportunities", status_code=201)
def create(contact_id: Id, body: Opportunity, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "opportunity-create", contact_id)
        if cached is not None:
            return cached
        validate(db, body, contact_id)
        stamp = now()
        cur = db.execute(
            "INSERT INTO crm_opportunities(contact_id,title,stage,expected_ttc,close_on,quote_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                contact_id,
                body.title,
                body.stage,
                body.expected_ttc,
                body.close_on,
                body.quote_id,
                stamp,
                stamp,
            ),
        )
        result = dict(
            db.execute(
                "SELECT * FROM crm_opportunities WHERE id=?", (cur.lastrowid,)
            ).fetchone()
        )
        event(
            db,
            contact_id,
            "OPPORTUNITY",
            json.dumps(
                {"motif": body.reason, "before": None, "after": result},
                ensure_ascii=False,
            ),
            user["id"],
        )
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.patch("/opportunities/{opportunity_id}")
def update(
    opportunity_id: Id, body: UpdateOpportunity, request: Request, user=Depends(editor)
):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(
            db, body, user, "opportunity-update", opportunity_id
        )
        if cached is not None:
            return cached
        old = db.execute(
            "SELECT * FROM crm_opportunities WHERE id=?", (opportunity_id,)
        ).fetchone()
        if not old:
            raise HTTPException(404, "Opportunité introuvable.")
        if old["version"] != body.expected_version:
            raise HTTPException(409, "Opportunité modifiée ; actualisez sa fiche.")
        validate(db, body, old["contact_id"])
        db.execute(
            "UPDATE crm_opportunities SET title=?,stage=?,expected_ttc=?,close_on=?,quote_id=?,version=version+1,updated_at=? WHERE id=?",
            (
                body.title,
                body.stage,
                body.expected_ttc,
                body.close_on,
                body.quote_id,
                now(),
                opportunity_id,
            ),
        )
        result = dict(
            db.execute(
                "SELECT * FROM crm_opportunities WHERE id=?", (opportunity_id,)
            ).fetchone()
        )
        event(
            db,
            old["contact_id"],
            "OPPORTUNITY",
            json.dumps(
                {"motif": body.reason, "before": dict(old), "after": result},
                ensure_ascii=False,
            ),
            user["id"],
        )
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
