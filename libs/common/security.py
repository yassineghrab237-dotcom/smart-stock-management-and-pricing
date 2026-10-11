import hashlib
import hmac
import secrets
import time
from fastapi import Depends, HTTPException, Request
from libs.common.database import connect, db_path

COOKIE = "smart_stock_session"


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 600000
    )
    return f"pbkdf2_sha256$600000${salt}${digest.hex()}"


def verify_password(password, stored):
    _, rounds, salt, expected = stored.split("$")
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
    )
    return hmac.compare_digest(digest.hex(), expected)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request):
    token = request.cookies.get(COOKIE, "")
    table = "sessions"
    authorization = request.headers.get("authorization")
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 256:
            raise HTTPException(401, "Connexion requise.")
        table = "mobile_sessions"
    with connect(db_path(request)) as db:
        row = db.execute(
            f"SELECT u.id,u.name,u.email,u.role FROM {table} s JOIN users u ON u.id=s.user_id LEFT JOIN user_access a ON a.user_id=u.id WHERE s.token_hash=? AND s.expires_at>? AND COALESCE(a.active,1)=1",
            (token_hash(token), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Connexion requise.")
    return dict(row)


def editor(user=Depends(current_user)):
    if user["role"] not in ("ADMIN", "MANAGER"):
        raise HTTPException(403, "Droits de modification requis.")
    return user


def admin(user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(403, "Droits administrateur requis.")
    return user
