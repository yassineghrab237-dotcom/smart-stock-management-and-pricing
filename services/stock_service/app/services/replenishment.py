"""Propositions min/max : stock, engagements, conditionnement et enveloppe HT."""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from services.stock_service.app.services.commerce import amount
from services.stock_service.app.services.insights import TUNIS


def plan(db, supplier_id, budget=None):
    today = datetime.now(TUNIS).date()
    incoming = {
        r["product_id"]: dict(r)
        for r in db.execute(
            """SELECT l.product_id,
        SUM(CASE WHEN o.status='DRAFT' THEN l.quantity ELSE 0 END) draft_units,
        SUM(CASE WHEN o.status!='DRAFT' THEN l.quantity-COALESCE(r.received,0) ELSE 0 END) incoming,
        SUM(CASE WHEN o.status!='DRAFT' AND o.expected_on < ? THEN l.quantity-COALESCE(r.received,0) ELSE 0 END) overdue
        FROM purchase_lines_local l JOIN purchase_orders_local o ON o.id=l.order_id
        LEFT JOIN (SELECT line_id,SUM(quantity) received FROM purchase_receipts_local GROUP BY line_id) r ON r.line_id=l.id
        WHERE o.status IN ('DRAFT','ORDERED','PART_RECEIVED') GROUP BY l.product_id""",
            (today.isoformat(),),
        )
    }
    rows = [
        dict(r)
        for r in db.execute(
            """SELECT p.id,p.sku,p.name,p.current_stock,p.threshold_min,p.threshold_max,p.version product_version,
        r.supplier_id,r.unit_cost_ht,r.lead_days,r.min_quantity,r.pack_size,r.enabled,r.version policy_version,
        c.name supplier_name,c.kind supplier_kind,c.stage supplier_stage,c.version supplier_version
        FROM products p LEFT JOIN replenishment_policies r ON r.product_id=p.id
        LEFT JOIN crm_contacts c ON c.id=r.supplier_id ORDER BY p.id"""
        )
    ]
    items = []
    for r in rows:
        if supplier_id is not None and r["supplier_id"] != supplier_id:
            continue
        r.update(incoming.get(r["id"], dict(draft_units=0, incoming=0, overdue=0)))
        position = r["current_stock"] + r["draft_units"] + r["incoming"]
        r.update(
            position=position,
            needed=0,
            quantity=0,
            total_ht="0.0000",
            reason="Stock et engagements suffisants",
        )
        if (
            not r["supplier_id"]
            or not r["enabled"]
            or r["supplier_kind"] == "CUSTOMER"
            or r["supplier_stage"] == "INACTIVE"
        ):
            r["reason"] = "Conditions fournisseur actives à renseigner"
        elif r["threshold_max"] is None or r["threshold_max"] <= r["threshold_min"]:
            r["reason"] = (
                "Seuil maximum supérieur au minimum requis dans la fiche produit"
            )
        elif position <= r["threshold_min"]:
            minimum = max(r["threshold_max"] - position, r["min_quantity"])
            r["needed"] = ((minimum + r["pack_size"] - 1) // r["pack_size"]) * r[
                "pack_size"
            ]
            if r["needed"] + position > 2147483647:
                r["reason"] = "Quantité hors limite du stock ; revoir les seuils"
                r["needed"] = 0
            else:
                r["reason"] = "Seuil minimum atteint ; compléter vers le maximum"
        items.append(r)
    items.sort(
        key=lambda r: (
            r["current_stock"] != 0,
            r["position"] - r["threshold_min"],
            r["sku"],
        )
    )
    left = Decimal(budget) if budget is not None else None
    spent = Decimal(0)
    for r in items:
        quantity = r["needed"]
        cost = (
            Decimal(r["unit_cost_ht"]) if r["unit_cost_ht"] is not None else Decimal(0)
        )
        if left is not None and quantity and cost > 0:
            affordable = int(left // cost)
            quantity = min(quantity, (affordable // r["pack_size"]) * r["pack_size"])
            if quantity < r["min_quantity"]:
                quantity = 0
            if quantity < r["needed"]:
                r["reason"] += " ; enveloppe insuffisante pour couvrir tout le besoin"
        r["quantity"] = quantity
        r["total_ht"] = amount(cost * quantity)
        spent += cost * quantity
        if left is not None:
            left -= cost * quantity
    snapshot = dict(
        supplier_id=supplier_id, budget=budget, today=today.isoformat(), items=items
    )
    fingerprint = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    lead = max((r["lead_days"] for r in items if r["quantity"]), default=0)
    return dict(
        items=items,
        total_ht=amount(spent),
        budget=budget,
        remaining_budget=None if left is None else amount(left),
        expected_on=(today + timedelta(days=lead)).isoformat(),
        fingerprint=fingerprint,
        supplier_id=supplier_id,
    )
