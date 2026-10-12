"""Sauvegardes locales réservées à l'administrateur."""

import re
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from libs.common.database import db_path
from libs.common.security import admin
from libs.common.maintenance import backup, verify, manifest_path

router = APIRouter(prefix="/maintenance", tags=["Sauvegardes locales"])


def directory(request):
    return Path(db_path(request)).resolve().parent / "backups"


@router.post("/backups", status_code=201)
def create(request: Request, user=Depends(admin)):
    filename = f"precios-{uuid4().hex}.sqlite3"
    try:
        result = backup(db_path(request), directory(request) / filename)
    except (ValueError, OSError):
        raise HTTPException(
            503,
            "Sauvegarde impossible ; vérifiez l’espace disque et les droits du dossier. Aucun fichier existant remplacé.",
        )
    return result


@router.get("/backups")
def listing(request: Request, user=Depends(admin)):
    folder = directory(request)
    items = []
    if folder.exists():
        for file in sorted(
            folder.glob("precios-*.sqlite3"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:30]:
            try:
                manifest = verify(file)
                items.append({**manifest, "verified": True})
            except (ValueError, OSError):
                items.append(dict(filename=file.name, verified=False))
    return {"items": items}


@router.get("/backups/{filename}/{part}")
def download(filename: str, part: str, request: Request, user=Depends(admin)):
    if not re.fullmatch(r"precios-[0-9a-f]{32}\.sqlite3", filename) or part not in (
        "database",
        "manifest",
    ):
        raise HTTPException(404, "Sauvegarde introuvable.")
    source = directory(request) / filename
    try:
        verify(source)
    except (ValueError, OSError):
        raise HTTPException(409, "Sauvegarde absente ou invalide.")
    target = source if part == "database" else manifest_path(source)
    return FileResponse(
        target,
        filename=target.name,
        media_type=(
            "application/octet-stream" if part == "database" else "application/json"
        ),
    )
