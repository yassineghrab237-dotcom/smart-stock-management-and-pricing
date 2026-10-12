from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.services.actions import actions
from services.stock_service.app.repositories.stock_repo import remember
from .crm import Mutation, replay

router = APIRouter(prefix="/actions", tags=["Suivi des décisions"])


class Decision(Mutation):
    action_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_event_id: int = Field(ge=0)
    status: Literal["TODO", "IN_PROGRESS", "ACKNOWLEDGED"]
    reason: str = Field(min_length=1, max_length=1000)


@router.get("")
def read(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        db.execute("BEGIN")
        return dict(
            items=actions(db),
            events=[
                dict(r)
                for r in db.execute(
                    "SELECT e.*,u.name actor_name FROM decision_events e JOIN users u ON u.id=e.actor_id ORDER BY e.id DESC LIMIT 100"
                )
            ],
        )


@router.post("/decisions")
def decide(body: Decision, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "decision")
        if cached is not None:
            return cached
        item = next((a for a in actions(db) if a["key"] == body.action_key), None)
        if not item:
            raise HTTPException(
                409, "La condition a changé ou a disparu ; actualisez les alertes."
            )
        if (
            item["decision"]["id"] if item["decision"] else 0
        ) != body.expected_event_id:
            raise HTTPException(409, "Le suivi a été modifié ; actualisez les alertes.")
        cursor = db.execute(
            "INSERT INTO decision_events(action_key,status,reason,actor_id,created_at) VALUES (?,?,?,?,?)",
            (body.action_key, body.status, body.reason, user["id"], now()),
        )
        result = dict(id=cursor.lastrowid)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
