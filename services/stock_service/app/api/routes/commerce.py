import sqlite3
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from libs.common.database import connect, db_path, now
from libs.common.security import current_user, editor
from services.stock_service.app.repositories.stock_repo import (
    product,
    check_version,
    existing_request,
    remember,
)
from services.stock_service.app.schemas.commerce_schemas import (
    DocumentInput,
    ConfirmInput,
    CancelInput,
    ReturnInput,
)
from services.stock_service.app.services.commerce import document, stock_change
from .crm import contact, event

router = APIRouter(prefix="/commerce", tags=["Ventes et devis"])
Id = Annotated[int, Path(ge=1, le=9223372036854775807)]


def replay(db, body, user, operation, identity=None):
    return existing_request(
        db,
        body.idempotency_key,
        user["id"],
        {"operation": operation, "identity": identity, **body.model_dump()},
    )


@router.get("/documents")
def documents(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT d.*,c.name customer_name FROM commercial_documents d LEFT JOIN crm_contacts c ON c.id=d.customer_id ORDER BY d.id DESC"
                )
            ]
        }


@router.get("/documents/{document_id}")
def get_document(document_id: Id, request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        result = document(db, document_id)
        result["products"] = [product(db, l["product_id"]) for l in result["lines"]]
        return result


@router.post("/documents", status_code=201)
def create(body: DocumentInput, request: Request, user=Depends(editor)):
    try:
        with connect(db_path(request), write=True) as db:
            cached, fingerprint = replay(db, body, user, "commercial-create")
            if cached is not None:
                return cached
            if db.execute(
                "SELECT 1 FROM sales_history WHERE reference=?", (body.reference,)
            ).fetchone():
                raise HTTPException(
                    409, "Référence déjà présente dans les ventes historiques."
                )
            if body.customer_id is not None:
                customer = contact(db, body.customer_id)
                if customer["kind"] == "SUPPLIER" or customer["stage"] == "INACTIVE":
                    raise HTTPException(
                        422, "Sélectionnez un client actif ou prospect."
                    )
            cursor = db.execute(
                "INSERT INTO commercial_documents(reference,kind,status,customer_id,note,created_at,actor_id) VALUES (?,?,'DRAFT',?,?,?,?)",
                (
                    body.reference,
                    body.kind,
                    body.customer_id,
                    body.note,
                    now(),
                    user["id"],
                ),
            )
            identity = cursor.lastrowid
            for line in body.lines:
                item = product(db, line.product_id)
                db.execute(
                    "INSERT INTO commercial_lines(document_id,product_id,sku,name,quantity,unit_price_ttc,discount_ttc,tax_rate,unit_cost_ht) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        identity,
                        item["id"],
                        item["sku"],
                        item["name"],
                        line.quantity,
                        line.unit_price_ttc,
                        line.discount_ttc,
                        line.tax_rate,
                        line.unit_cost_ht,
                    ),
                )
            if body.customer_id is not None:
                event(
                    db,
                    body.customer_id,
                    "COMMERCIAL",
                    f"Brouillon {body.reference} créé",
                    user["id"],
                )
            result = document(db, identity)
            remember(db, body.idempotency_key, user["id"], fingerprint, result)
            return result
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Référence commerciale déjà utilisée.")


@router.post("/documents/{document_id}/confirm")
def confirm(
    document_id: Id, body: ConfirmInput, request: Request, user=Depends(editor)
):
    try:
        with connect(db_path(request), write=True) as db:
            cached, fingerprint = replay(
                db, body, user, "commercial-confirm", document_id
            )
            if cached is not None:
                return cached
            draft = document(db, document_id)
            check_version(draft, body.expected_version)
            if draft["status"] != "DRAFT":
                raise HTTPException(409, "Ce document n'est plus un brouillon.")
            identity = document_id
            if draft["kind"] == "QUOTE":
                if not body.sale_reference:
                    raise HTTPException(
                        422, "Référence de vente requise pour convertir ce devis."
                    )
                if db.execute(
                    "SELECT 1 FROM sales_history WHERE reference=?",
                    (body.sale_reference,),
                ).fetchone():
                    raise HTTPException(
                        409, "Référence déjà présente dans les ventes historiques."
                    )
                cursor = db.execute(
                    "INSERT INTO commercial_documents(reference,kind,status,customer_id,note,source_quote_id,created_at,actor_id) VALUES (?,'SALE','DRAFT',?,?,?,?,?)",
                    (
                        body.sale_reference,
                        draft["customer_id"],
                        draft["note"],
                        document_id,
                        now(),
                        user["id"],
                    ),
                )
                identity = cursor.lastrowid
                db.execute(
                    "INSERT INTO commercial_lines(document_id,product_id,sku,name,quantity,unit_price_ttc,discount_ttc,tax_rate,unit_cost_ht) SELECT ?,product_id,sku,name,quantity,unit_price_ttc,discount_ttc,tax_rate,unit_cost_ht FROM commercial_lines WHERE document_id=?",
                    (identity, document_id),
                )
                db.execute(
                    "UPDATE commercial_documents SET status='CONVERTED',version=version+1 WHERE id=?",
                    (document_id,),
                )
            reference = (
                body.sale_reference if draft["kind"] == "QUOTE" else draft["reference"]
            )
            for line in draft["lines"]:
                version = body.product_versions.get(str(line["product_id"]))
                if version is None or version < 1:
                    raise HTTPException(
                        422, "Actualisez les stocks avant de confirmer."
                    )
                stock_change(
                    db,
                    line["product_id"],
                    -line["quantity"],
                    user["id"],
                    f"Vente {reference}",
                    version,
                )
            db.execute(
                "UPDATE commercial_documents SET status='CONFIRMED',version=version+1,confirmed_at=? WHERE id=?",
                (now(), identity),
            )
            if draft["customer_id"] is not None:
                event(
                    db,
                    draft["customer_id"],
                    "COMMERCIAL",
                    f"Vente {reference} confirmée",
                    user["id"],
                )
            result = document(db, identity)
            remember(db, body.idempotency_key, user["id"], fingerprint, result)
            return result
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, "Référence de vente déjà utilisée ou devis déjà converti."
        )


@router.post("/documents/{document_id}/cancel")
def cancel(document_id: Id, body: CancelInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "commercial-cancel", document_id)
        if cached is not None:
            return cached
        draft = document(db, document_id)
        check_version(draft, body.expected_version)
        if draft["status"] != "DRAFT":
            raise HTTPException(
                409, "Une vente confirmée doit faire l'objet d'un retour."
            )
        db.execute(
            "UPDATE commercial_documents SET status='CANCELLED',version=version+1,note=note || ? WHERE id=?",
            ("\nAnnulation : " + body.reason, document_id),
        )
        if draft["customer_id"] is not None:
            event(
                db,
                draft["customer_id"],
                "COMMERCIAL",
                f"Document {draft['reference']} annulé : {body.reason}",
                user["id"],
            )
        result = document(db, document_id)
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result


@router.post("/lines/{line_id}/returns", status_code=201)
def return_line(line_id: Id, body: ReturnInput, request: Request, user=Depends(editor)):
    with connect(db_path(request), write=True) as db:
        cached, fingerprint = replay(db, body, user, "commercial-return", line_id)
        if cached is not None:
            return cached
        row = db.execute(
            "SELECT * FROM commercial_lines WHERE id=?", (line_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Ligne de vente introuvable.")
        sale = document(db, row["document_id"])
        if sale["kind"] != "SALE" or sale["status"] != "CONFIRMED":
            raise HTTPException(409, "Le retour exige une vente confirmée.")
        line = next(l for l in sale["lines"] if l["id"] == line_id)
        if body.quantity > line["quantity"] - line["returned"]:
            raise HTTPException(409, "Quantité supérieure au solde retournable.")
        check_version(product(db, line["product_id"]), body.expected_product_version)
        if body.restock:
            stock_change(
                db,
                line["product_id"],
                body.quantity,
                user["id"],
                f"Retour vente {sale['reference']} : {body.reason}",
                body.expected_product_version,
            )
        db.execute(
            "INSERT INTO commercial_returns(line_id,quantity,restock,reason,actor_id,created_at) VALUES (?,?,?,?,?,?)",
            (line_id, body.quantity, body.restock, body.reason, user["id"], now()),
        )
        db.execute(
            "UPDATE commercial_documents SET version=version+1 WHERE id=?",
            (sale["id"],),
        )
        if sale["customer_id"] is not None:
            event(
                db,
                sale["customer_id"],
                "RETURN",
                f"Retour de {body.quantity} unité(s), vente {sale['reference']} : {body.reason}",
                user["id"],
            )
        result = document(db, sale["id"])
        remember(db, body.idempotency_key, user["id"], fingerprint, result)
        return result
