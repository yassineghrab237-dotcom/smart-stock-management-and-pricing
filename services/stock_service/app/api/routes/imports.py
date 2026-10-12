"""Import explicite : aperçu sans écriture puis transaction intégrale."""

import csv
import hashlib
import io
import json
import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.schemas.product_schemas import (
    ProductInput,
    normalize_price,
)

from services.stock_service.app.services.transaction_import import preview_transactions, commit_transactions

router = APIRouter(prefix="/imports", tags=["Imports CSV"])


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["catalogue", "sales", "transactions"]
    csv_text: str = Field(min_length=1, max_length=1000000)
    filename: str = Field(default="import.csv", min_length=1, max_length=180)
    delimiter: Literal[",", ";"] = ","


class ImportCommit(ImportInput):
    preview_token: str = Field(min_length=64, max_length=64)


def digest(body):
    # Le nom du fichier ne permet pas de réimporter le même contenu.
    return hashlib.sha256(
        (body.delimiter + body.csv_text.lstrip("\ufeff")).encode()
    ).hexdigest()


def integer(value):
    if not re.fullmatch(r"[0-9]{1,10}", value):
        raise ValueError("Entier positif requis")
    return int(value)


def preview(db, body):
    if body.kind == "transactions":
        return preview_transactions(db, body)
    reader = csv.reader(
        io.StringIO(body.csv_text.lstrip("\ufeff")),
        delimiter=body.delimiter,
        strict=True,
    )
    required = (
        {"sku", "name"}
        if body.kind == "catalogue"
        else {"reference", "sku", "sold_on", "quantity", "unit_price"}
    )
    allowed = set(ProductInput.model_fields) if body.kind == "catalogue" else required
    try:
        headers = [h.strip() for h in next(reader)]
        if (
            len(set(headers)) != len(headers)
            or not required.issubset(headers)
            or not set(headers).issubset(allowed)
        ):
            raise HTTPException(
                422,
                "Colonnes requises manquantes, inconnues ou dupliquées. Consultez le modèle CSV.",
            )
        rows = []
        seen = set()
        for values in reader:
            if not values or all(not v.strip() for v in values):
                continue
            if len(rows) >= 1000:
                raise HTTPException(422, "Maximum 1 000 lignes par import.")
            entry = {
                "line": reader.line_num,
                "sku": "",
                "label": "",
                "data": None,
                "errors": [],
            }
            try:
                if len(values) != len(headers):
                    raise ValueError("Nombre de cellules différent des colonnes")
                data = dict(zip(headers, (v.strip() for v in values)))
                entry["sku"] = data["sku"]
                key = data["sku"] if body.kind == "catalogue" else data["reference"]
                if key in seen:
                    raise ValueError("Référence dupliquée dans le fichier")
                seen.add(key)
                product = db.execute(
                    "SELECT id,sku,name,version FROM products WHERE sku=?",
                    (data["sku"],),
                ).fetchone()
                if body.kind == "catalogue":
                    if product:
                        raise ValueError(
                            "SKU déjà présent : aucun produit existant ne sera remplacé"
                        )
                    for field in list(data):
                        if field not in ("sku", "name"):
                            if not data[field]:
                                data.pop(field)
                            elif field in ("threshold_min", "threshold_max"):
                                data[field] = integer(data[field])
                    data = ProductInput.model_validate(data).model_dump()
                    entry["label"] = data["name"]
                else:
                    if not product:
                        raise ValueError(
                            "SKU introuvable : créez le produit avant d’importer ses ventes"
                        )
                    if not data["reference"] or len(data["reference"]) > 120:
                        raise ValueError(
                            "Référence de vente requise, maximum 120 caractères"
                        )
                    if db.execute(
                        "SELECT 1 FROM sales_history WHERE reference=?",
                        (data["reference"],),
                    ).fetchone():
                        raise ValueError("Référence de vente déjà importée")
                    if db.execute("SELECT 1 FROM commercial_documents WHERE reference=?", (data["reference"],)).fetchone():
                        raise ValueError("Référence déjà présente dans les documents commerciaux")
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["sold_on"]):
                        raise ValueError("Date attendue : AAAA-MM-JJ")
                    sold_on = date.fromisoformat(data["sold_on"])
                    if sold_on > date.today():
                        raise ValueError("Date de vente future refusée")
                    data["quantity"] = integer(data["quantity"])
                    if not 1 <= data["quantity"] <= 2147483647:
                        raise ValueError("Quantité entre 1 et 2147483647 requise")
                    data["unit_price"] = normalize_price(data["unit_price"])
                    data["product_id"] = product["id"]
                    data["product_version"] = product["version"]
                    entry["label"] = product["name"]
                entry["data"] = data
            except ValidationError as exc:
                entry["errors"] = [
                    " / ".join(str(v) for v in e["loc"]) + ": " + e["msg"]
                    for e in exc.errors(include_input=False)
                ]
            except ValueError as exc:
                entry["errors"] = [str(exc)]
            rows.append(entry)
    except (csv.Error, StopIteration):
        raise HTTPException(422, "CSV vide ou mal formé.")
    if not rows:
        raise HTTPException(422, "Le CSV ne contient aucune ligne de données.")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"kind": body.kind, "digest": digest(body), "rows": rows},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return {
        "rows": rows,
        "count": len(rows),
        "valid": all(not r["errors"] for r in rows),
        "preview_token": fingerprint,
    }


@router.post("/preview")
def inspect(body: ImportInput, request: Request, user=Depends(editor)):
    with connect(db_path(request)) as db:
        result = preview(db, body)
        existing = db.execute(
            "SELECT id FROM csv_imports WHERE kind=? AND digest=?",
            (body.kind, digest(body)),
        ).fetchone()
        if existing:
            result["valid"] = False
            result["message"] = "Ce fichier a déjà été importé."
        return result


@router.post("/commit")
def commit(body: ImportCommit, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        prior = db.execute(
            "SELECT id,row_count FROM csv_imports WHERE kind=? AND digest=?",
            (body.kind, digest(body)),
        ).fetchone()
        if prior:
            return {
                "id": prior["id"],
                "count": prior["row_count"],
                "already_imported": True,
            }
        result = preview(db, body)
        if result["preview_token"] != body.preview_token:
            raise HTTPException(
                409,
                "Le fichier ou les produits ont changé. Analysez à nouveau avant de confirmer.",
            )
        if not result["valid"]:
            raise HTTPException(
                422,
                "Corrigez toutes les lignes avant l’import. Aucune donnée enregistrée.",
            )
        stamp = now()
        cursor = db.execute(
            "INSERT INTO csv_imports(kind,digest,filename,row_count,actor_id,created_at) VALUES (?,?,?,?,?,?)",
            (
                body.kind,
                digest(body),
                body.filename,
                result["count"],
                user["id"],
                stamp,
            ),
        )
        import_id = cursor.lastrowid
        if body.kind == "transactions":
            commit_transactions(db, result["rows"], user["id"], stamp, import_id)
            return {"id": import_id, "count": result["count"], "already_imported": False}
        for entry in result["rows"]:
            data = entry["data"]
            if body.kind == "catalogue":
                columns = list(data) + ["created_at", "updated_at"]
                db.execute(
                    f"INSERT INTO products({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    [*data.values(), stamp, stamp],
                )
            else:
                db.execute(
                    "INSERT INTO sales_history(reference,product_id,sold_on,quantity,unit_price,import_id) VALUES (?,?,?,?,?,?)",
                    (
                        data["reference"],
                        data["product_id"],
                        data["sold_on"],
                        data["quantity"],
                        data["unit_price"],
                        import_id,
                    ),
                )
        return {"id": import_id, "count": result["count"], "already_imported": False}


@router.get("")
def history(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT i.id,i.kind,i.filename,i.row_count,i.created_at,u.name actor_name FROM csv_imports i JOIN users u ON u.id=i.actor_id ORDER BY i.id DESC LIMIT 100"
                )
            ]
        }


@router.get("/sales")
def sales(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT s.id,s.reference,s.sold_on,s.quantity,s.unit_price,p.sku,p.name product_name FROM sales_history s JOIN products p ON p.id=s.product_id ORDER BY s.sold_on DESC,s.id DESC LIMIT 100"
                )
            ]
        }
