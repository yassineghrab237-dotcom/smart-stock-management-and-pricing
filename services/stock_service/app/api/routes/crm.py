"""Contacts commerciaux et suivi local ; aucun envoi de message externe."""

import json
import re
from datetime import date
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.repositories.stock_repo import (
    existing_request,
    remember,
    check_version,
)

router = APIRouter(prefix="/crm", tags=["Relation clients et fournisseurs"])
Id = Annotated[int, Path(ge=1, le=9223372036854775807)]


class Mutation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ContactInput(Mutation):
    name: str = Field(min_length=1, max_length=180)
    kind: Literal["CUSTOMER", "SUPPLIER", "BOTH"] = "CUSTOMER"
    company: str = Field(default="", max_length=180)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=60)
    address: str = Field(default="", max_length=1000)
    stage: Literal["PROSPECT", "ACTIVE", "INACTIVE"] = "PROSPECT"
    contact_permission: Literal["UNKNOWN", "ALLOWED", "REFUSED"] = "UNKNOWN"
    lead_days: int = Field(default=0, ge=0, le=3650)
    min_order: int = Field(default=1, ge=1, le=1000000)

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Email invalide")
        return value


class ContactUpdate(ContactInput):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class NoteInput(Mutation):
    detail: str = Field(min_length=1, max_length=4000)


class TaskInput(Mutation):
    title: str = Field(min_length=1, max_length=300)
    due_on: str = Field(max_length=10)

    @field_validator("due_on")
    @classmethod
    def valid_date(cls, value):
        return date.fromisoformat(value).isoformat()


class TaskUpdate(Mutation):
    expected_version: int = Field(ge=1)
    status: Literal["TODO", "DONE", "CANCELLED"]


def contact(db, contact_id):
    row = db.execute("SELECT * FROM crm_contacts WHERE id=?", (contact_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Contact introuvable.")
    return dict(row)


def event(db, contact_id, kind, detail, actor):
    db.execute(
        "INSERT INTO crm_events(contact_id,kind,detail,actor_id,created_at) VALUES (?,?,?,?,?)",
        (contact_id, kind, detail, actor, now()),
    )


def replay(db, body, user, operation, identity=None):
    return existing_request(
        db,
        body.idempotency_key,
        user["id"],
        {"operation": operation, "identity": identity, **body.model_dump()},
    )


@router.get("/contacts")
def contacts(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute("SELECT * FROM crm_contacts ORDER BY name,id")
            ]
        }


@router.get("/contacts/{contact_id}")
def detail(contact_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        result = contact(db, contact_id)
        result["events"] = [
            dict(r)
            for r in db.execute(
                "SELECT e.*,u.name actor_name FROM crm_events e JOIN users u ON u.id=e.actor_id WHERE contact_id=? ORDER BY e.id DESC",
                (contact_id,),
            )
        ]
        result["tasks"] = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM crm_tasks WHERE contact_id=? ORDER BY due_on,id",
                (contact_id,),
            )
        ]
        return result


@router.post("/contacts", status_code=201)
def create(body: ContactInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "crm-create")
        if cached is not None:
            return cached
        fields = body.model_dump(exclude={"idempotency_key"})
        fields.update(created_at=now(), updated_at=now())
        cursor = db.execute(
            f"INSERT INTO crm_contacts({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            list(fields.values()),
        )
        event(db, cursor.lastrowid, "CREATED", "Fiche créée", user["id"])
        result = contact(db, cursor.lastrowid)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.patch("/contacts/{contact_id}")
def update(contact_id: Id, body: ContactUpdate, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "crm-update", contact_id)
        if cached is not None:
            return cached
        before = contact(db, contact_id)
        check_version(before, body.expected_version)
        fields = body.model_dump(
            exclude={"idempotency_key", "expected_version", "reason"}
        )
        fields["updated_at"] = now()
        db.execute(
            f"UPDATE crm_contacts SET {','.join(k+'=?' for k in fields)},version=version+1 WHERE id=?",
            [*fields.values(), contact_id],
        )
        changes = {
            k: {"avant": before[k], "après": v}
            for k, v in fields.items()
            if k != "updated_at" and before[k] != v
        }
        event(
            db,
            contact_id,
            "UPDATED",
            json.dumps(
                {"motif": body.reason, "changements": changes}, ensure_ascii=False
            ),
            user["id"],
        )
        result = contact(db, contact_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/contacts/{contact_id}/notes", status_code=201)
def add_note(contact_id: Id, body: NoteInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "crm-note", contact_id)
        if cached is not None:
            return cached
        contact(db, contact_id)
        event(db, contact_id, "NOTE", body.detail, user["id"])
        result = {"saved": True}
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/contacts/{contact_id}/tasks", status_code=201)
def add_task(contact_id: Id, body: TaskInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "crm-task", contact_id)
        if cached is not None:
            return cached
        contact(db, contact_id)
        stamp = now()
        cursor = db.execute(
            "INSERT INTO crm_tasks(contact_id,title,due_on,status,actor_id,created_at,updated_at) VALUES (?,?,?,'TODO',?,?,?)",
            (contact_id, body.title, body.due_on, user["id"], stamp, stamp),
        )
        event(
            db,
            contact_id,
            "TASK",
            f"Tâche : {body.title} — échéance {body.due_on}",
            user["id"],
        )
        result = {"id": cursor.lastrowid}
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.patch("/tasks/{task_id}")
def task_status(task_id: Id, body: TaskUpdate, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "crm-task-status", task_id)
        if cached is not None:
            return cached
        row = db.execute("SELECT * FROM crm_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Tâche introuvable.")
        check_version(dict(row), body.expected_version)
        db.execute(
            "UPDATE crm_tasks SET status=?,version=version+1,updated_at=? WHERE id=?",
            (body.status, now(), task_id),
        )
        event(
            db,
            row["contact_id"],
            "TASK_STATUS",
            f"{row['title']} : {row['status']} → {body.status}",
            user["id"],
        )
        result = {"id": task_id, "status": body.status, "version": row["version"] + 1}
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
