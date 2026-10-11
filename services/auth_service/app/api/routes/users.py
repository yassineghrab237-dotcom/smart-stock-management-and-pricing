import sqlite3
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Path
from pydantic import BaseModel, ConfigDict, Field
from libs.common.database import connect, db_path, now
from libs.common.security import admin, hash_password
from services.auth_service.app.schemas.auth_schemas import CreateUser

router = APIRouter(prefix="/auth/users", tags=["Utilisateurs"])


@router.get("")
def users(request: Request, user=Depends(admin)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                {**dict(r), "active": bool(r["active"])}
                for r in db.execute(
                    "SELECT u.id,u.name,u.email,u.role,COALESCE(a.active,1) active FROM users u LEFT JOIN user_access a ON a.user_id=u.id ORDER BY u.id"
                )
            ]
        }


@router.post("", status_code=201)
def create(body: CreateUser, request: Request, user=Depends(admin)):
    password_hash = hash_password(body.password)
    try:
        with connect(db_path(request), write=True) as db:
            cursor = db.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                (body.name, body.email, password_hash, body.role, now()),
            )
            return dict(
                db.execute(
                    "SELECT id,name,email,role FROM users WHERE id=?",
                    (cursor.lastrowid,),
                ).fetchone()
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Cette adresse email est déjà utilisée.")


class AccessInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    active: bool
    reason: str = Field(min_length=1, max_length=1000)


UserId = Annotated[int, Path(ge=1, le=9223372036854775807)]


def revoke(db, user_id):
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM mobile_sessions WHERE user_id=?", (user_id,))


@router.post("/{user_id}/access")
def access(user_id: UserId, body: AccessInput, request: Request, user=Depends(admin)):
    if not body.reason.strip():
        raise HTTPException(422, "Un motif est nécessaire.")
    with connect(db_path(request), write=True) as db:
        row = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Compte introuvable.")
        if not body.active:
            if user_id == user["id"]:
                raise HTTPException(
                    409, "Vous ne pouvez pas désactiver votre propre compte."
                )
            active_admins = db.execute(
                "SELECT COUNT(*) FROM users u LEFT JOIN user_access a ON a.user_id=u.id WHERE u.role='ADMIN' AND COALESCE(a.active,1)=1"
            ).fetchone()[0]
            if row["role"] == "ADMIN" and active_admins <= 1:
                raise HTTPException(409, "Un administrateur actif doit être conservé.")
        db.execute(
            "INSERT INTO user_access(user_id,active,reason,actor_id,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET active=excluded.active,reason=excluded.reason,actor_id=excluded.actor_id,updated_at=excluded.updated_at",
            (user_id, int(body.active), body.reason.strip(), user["id"], now()),
        )
        if not body.active:
            revoke(db, user_id)
    return {
        "detail": (
            "Compte réactivé. Une nouvelle connexion est nécessaire."
            if body.active
            else "Compte désactivé et sessions web/mobile révoquées."
        )
    }


@router.post("/{user_id}/revoke-sessions")
def revoke_sessions(user_id: UserId, request: Request, user=Depends(admin)):
    with connect(db_path(request), write=True) as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(404, "Compte introuvable.")
        revoke(db, user_id)
    return {"detail": "Sessions web et mobile révoquées. Le compte est conservé."}
