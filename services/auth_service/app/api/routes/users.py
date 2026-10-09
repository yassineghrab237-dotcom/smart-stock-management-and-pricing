import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Request
from libs.common.database import connect, db_path, now
from libs.common.security import admin, hash_password
from services.auth_service.app.schemas.auth_schemas import CreateUser

router = APIRouter(prefix="/auth/users", tags=["Utilisateurs"])


@router.get("")
def users(request: Request, user=Depends(admin)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute("SELECT id,name,email,role FROM users ORDER BY id")
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
