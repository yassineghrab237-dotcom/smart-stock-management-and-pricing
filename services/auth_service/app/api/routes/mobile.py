"""Jetons natifs séparés des cookies web ; jamais de secret partagé embarqué."""

import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from libs.common.database import connect, db_path
from libs.common.security import current_user, token_hash
from services.auth_service.app.schemas.auth_schemas import Login
from services.auth_service.app.api.routes.auth import authenticate

router = APIRouter(prefix="/mobile/auth", tags=["Connexion mobile"])


@router.post("/login")
def login(body: Login, request: Request):
    # HTTP uniquement pour le test par tunnel USB loopback ; TLS requis hors PC.
    if request.url.scheme != "https" and (
        request.url.hostname not in ("127.0.0.1", "localhost", "testserver")
        or request.client is None
        or request.client.host not in ("127.0.0.1", "::1", "testclient")
    ):
        raise HTTPException(403, "HTTPS requis pour la connexion mobile distante.")
    with connect(db_path(request), write=True) as db:
        user_id = authenticate(body, request, db)
        token = secrets.token_urlsafe(48)
        expires_at = time.time() + 43200
        db.execute(
            "INSERT INTO mobile_sessions VALUES (?,?,?)",
            (token_hash(token), user_id, expires_at),
        )
        user = dict(
            db.execute(
                "SELECT id,name,email,role FROM users WHERE id=?", (user_id,)
            ).fetchone()
        )
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "user": user,
        }


@router.post("/logout")
def logout(request: Request, user=Depends(current_user)):
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Jeton mobile requis.")
    with connect(db_path(request), write=True) as db:
        db.execute(
            "DELETE FROM mobile_sessions WHERE token_hash=?", (token_hash(token),)
        )
    return {"detail": "Déconnexion mobile effectuée."}
