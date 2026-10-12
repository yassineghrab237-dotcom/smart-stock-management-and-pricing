"""Import des ventes opérationnelles : aperçu fiscal et stock, puis lot atomique."""

import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import date, datetime
from fastapi import HTTPException
from pydantic import ValidationError
from services.stock_service.app.schemas.commerce_schemas import SaleLine
from services.stock_service.app.services.insights import TUNIS
from services.stock_service.app.services.commerce import stock_change

REQUIRED = {"reference", "sku", "sold_on", "quantity", "unit_price_ttc", "tax_rate"}
OPTIONAL = {"discount_ttc", "unit_cost_ht", "customer_id"}


def preview_transactions(db, body):
    reader = csv.reader(
        io.StringIO(body.csv_text.lstrip("\ufeff")),
        delimiter=body.delimiter,
        strict=True,
    )
    rows = []
    seen = set()
    metadata = {}
    totals = defaultdict(int)
    line_counts = defaultdict(int)
    try:
        headers = [v.strip() for v in next(reader)]
        if (
            len(set(headers)) != len(headers)
            or not REQUIRED.issubset(headers)
            or not set(headers).issubset(REQUIRED | OPTIONAL)
        ):
            raise HTTPException(
                422,
                "Colonnes manquantes, inconnues ou dupliquées. Utilisez le modèle ventes avec sortie de stock.",
            )
        for cells in reader:
            if not cells or all(not v.strip() for v in cells):
                continue
            if len(rows) >= 1000:
                raise HTTPException(422, "Maximum 1 000 lignes par import.")
            entry = dict(line=reader.line_num, sku="", label="", data=None, errors=[])
            try:
                if len(cells) != len(headers):
                    raise ValueError("Nombre de cellules incorrect")
                raw = dict(zip(headers, (v.strip() for v in cells)))
                entry["sku"] = raw["sku"]
                ref = raw["reference"]
                if not ref or len(ref) > 100:
                    raise ValueError("Référence requise, maximum 100 caractères")
                if (ref, raw["sku"]) in seen:
                    raise ValueError(
                        "SKU dupliqué dans cette vente ; regroupez la quantité"
                    )
                seen.add((ref, raw["sku"]))
                if (
                    db.execute(
                        "SELECT 1 FROM commercial_documents WHERE reference=?", (ref,)
                    ).fetchone()
                    or db.execute(
                        "SELECT 1 FROM sales_history WHERE reference=?", (ref,)
                    ).fetchone()
                ):
                    raise ValueError(
                        "Référence déjà enregistrée comme document ou vente historique"
                    )
                p = db.execute(
                    "SELECT id,name,version,current_stock FROM products WHERE sku=?",
                    (raw["sku"],),
                ).fetchone()
                if not p:
                    raise ValueError("SKU introuvable")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw["sold_on"]):
                    raise ValueError("Date attendue : AAAA-MM-JJ")
                sold_on = date.fromisoformat(raw["sold_on"])
                if sold_on > datetime.now(TUNIS).date():
                    raise ValueError("Date future refusée")
                if not re.fullmatch(r"[0-9]{1,10}", raw["quantity"]):
                    raise ValueError("Quantité entière positive requise")
                customer = None
                customer_version = None
                if raw.get("customer_id"):
                    if not re.fullmatch(r"[0-9]{1,18}", raw["customer_id"]):
                        raise ValueError("Identifiant CRM invalide")
                    customer = int(raw["customer_id"])
                    c = db.execute(
                        "SELECT kind,stage,version FROM crm_contacts WHERE id=?",
                        (customer,),
                    ).fetchone()
                    if not c or c["kind"] == "SUPPLIER" or c["stage"] == "INACTIVE":
                        raise ValueError("Client CRM introuvable ou inactif")
                    customer_version = c["version"]
                meta = (sold_on.isoformat(), customer)
                if ref in metadata and metadata[ref] != meta:
                    raise ValueError(
                        "Une vente doit avoir une date et un client identiques sur toutes ses lignes"
                    )
                metadata[ref] = meta
                line = SaleLine(
                    product_id=p["id"],
                    quantity=int(raw["quantity"]),
                    unit_price_ttc=raw["unit_price_ttc"],
                    tax_rate=raw["tax_rate"],
                    discount_ttc=raw.get("discount_ttc") or "0",
                    unit_cost_ht=raw.get("unit_cost_ht") or None,
                ).model_dump()
                line_counts[ref] += 1
                if line_counts[ref] > 100:
                    raise ValueError("Maximum 100 produits par vente")
                totals[p["id"]] += line["quantity"]
                entry["data"] = {
                    **line,
                    "reference": ref,
                    "sku": raw["sku"],
                    "sold_on": meta[0],
                    "customer_id": customer,
                    "customer_version": customer_version,
                    "product_version": p["version"],
                    "stock_before": p["current_stock"],
                }
                entry["label"] = p["name"]
            except ValidationError as exc:
                entry["errors"] = [
                    " / ".join(str(x) for x in e["loc"]) + ": " + e["msg"]
                    for e in exc.errors(include_input=False)
                ]
            except ValueError as exc:
                entry["errors"] = [str(exc)]
            rows.append(entry)
    except (csv.Error, StopIteration):
        raise HTTPException(422, "CSV vide ou mal formé.")
    if not rows:
        raise HTTPException(422, "Aucune ligne de données.")
    for entry in rows:
        d = entry["data"]
        if d:
            d["stock_after_batch"] = d["stock_before"] - totals[d["product_id"]]
            if d["stock_after_batch"] < 0:
                entry["errors"].append(
                    "Stock insuffisant pour le total des ventes de ce produit dans le fichier"
                )
    fingerprint = hashlib.sha256(
        json.dumps(
            dict(
                kind="transactions",
                content=body.csv_text.lstrip("\ufeff"),
                delimiter=body.delimiter,
                rows=rows,
            ),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return dict(
        rows=rows,
        count=len(rows),
        valid=all(not e["errors"] for e in rows),
        preview_token=fingerprint,
    )


def commit_transactions(db, rows, actor, stamp, import_id):
    docs = {}
    for entry in rows:
        d = entry["data"]
        ref = d["reference"]
        if ref not in docs:
            cursor = db.execute(
                "INSERT INTO commercial_documents(reference,kind,status,customer_id,note,created_at,confirmed_at,actor_id,version) VALUES (?,'SALE','CONFIRMED',?,?,?,?,?,2)",
                (
                    ref,
                    d["customer_id"],
                    f"Import CSV opérationnel #{import_id}",
                    stamp,
                    stamp,
                    actor,
                ),
            )
            docs[ref] = cursor.lastrowid
            db.execute(
                "INSERT INTO commercial_sale_dates(document_id,sold_on) VALUES (?,?)",
                (docs[ref], d["sold_on"]),
            )
            if d["customer_id"] is not None:
                db.execute(
                    "INSERT INTO crm_events(contact_id,kind,detail,actor_id,created_at) VALUES (?,'COMMERCIAL',?,?,?)",
                    (
                        d["customer_id"],
                        f"Vente {ref} importée avec sortie de stock",
                        actor,
                        stamp,
                    ),
                )
        db.execute(
            "INSERT INTO commercial_lines(document_id,product_id,sku,name,quantity,unit_price_ttc,discount_ttc,tax_rate,unit_cost_ht) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                docs[ref],
                d["product_id"],
                d["sku"],
                entry["label"],
                d["quantity"],
                d["unit_price_ttc"],
                d["discount_ttc"],
                d["tax_rate"],
                d["unit_cost_ht"],
            ),
        )
        version = db.execute(
            "SELECT version FROM products WHERE id=?", (d["product_id"],)
        ).fetchone()["version"]
        stock_change(
            db, d["product_id"], -d["quantity"], actor, f"Vente CSV {ref}", version
        )
