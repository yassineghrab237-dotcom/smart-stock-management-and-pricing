import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from libs.common.database import connect, db_path, now
from libs.common.security import (
    COOKIE,
    current_user,
    hash_password,
    token_hash,
    verify_password,
)
from services.auth_service.app.schemas.auth_schemas import Login, Setup

router = APIRouter(prefix="/auth", tags=["Authentification"])


def session(db, response, request, user_id):
    token = secrets.token_urlsafe(48)
    db.execute(
        "INSERT INTO sessions VALUES (?,?,?)",
        (token_hash(token), user_id, time.time() + 43200),
    )
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=43200,
        path="/",
    )
    return dict(
        db.execute(
            "SELECT id,name,email,role FROM users WHERE id=?", (user_id,)
        ).fetchone()
    )


@router.get("/setup")
def setup_status(request: Request):
    with connect(db_path(request)) as db:
        return {"required": db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0}


@router.post("/setup", status_code=201)
def setup(body: Setup, request: Request, response: Response):
    password_hash = hash_password(body.password)
    with connect(db_path(request), write=True) as db:
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            raise HTTPException(409, "La configuration initiale est déjà terminée.")
        cursor = db.execute(
            "INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,'ADMIN',?)",
            (body.name, body.email, password_hash, now()),
        )
        return session(db, response, request, cursor.lastrowid)


def authenticate(body: Login, request: Request, db):
    client_ip = request.client.host if request.client else "local"
    identities = (f"ip:{client_ip}", f"email:{body.email}")
    stamp = time.time()
    counts = [
        db.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE identity=? AND attempted_at>?",
            (identity, stamp - 900),
        ).fetchone()[0]
        for identity in identities
    ]
    if max(counts) >= 5:
        raise HTTPException(429, "Trop de tentatives. Réessayez dans 15 minutes.")
    row = db.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    # Fixed unusable hash gives unknown users the same PBKDF2 work factor.
    dummy_hash = "pbkdf2_sha256$600000$" + "00" * 16 + "$" + "00" * 32
    valid = verify_password(body.password, row["password_hash"] if row else dummy_hash)
    if row:
        access = db.execute(
            "SELECT active FROM user_access WHERE user_id=?", (row["id"],)
        ).fetchone()
        if access and not access["active"]:
            valid = False
    if not row or not valid:
        db.executemany(
            "INSERT INTO login_attempts(identity,attempted_at) VALUES (?,?)",
            [(identity, stamp) for identity in identities],
        )
        # Commit failure attempts before raising the HTTP error.
        db.commit()
        raise HTTPException(401, "Email ou mot de passe incorrect.")
    return row["id"]


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    with connect(db_path(request), write=True) as db:
        return session(db, response, request, authenticate(body, request, db))


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.post("/logout")
def logout(request: Request, response: Response, user=Depends(current_user)):
    with connect(db_path(request), write=True) as db:
        db.execute(
            "DELETE FROM sessions WHERE token_hash=?",
            (token_hash(request.cookies.get(COOKIE, "")),),
        )
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return {"detail": "Déconnexion effectuée."}
