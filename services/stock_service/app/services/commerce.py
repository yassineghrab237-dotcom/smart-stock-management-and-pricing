"""Montants commerciaux explicites TND ; aucune facture fiscale générée."""

from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from libs.common.database import now
from services.stock_service.app.repositories.stock_repo import product, check_version


def amount(value):
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def line_totals(line, quantity=None):
    quantity = line["quantity"] if quantity is None else quantity
    ttc = (Decimal(line["unit_price_ttc"]) - Decimal(line["discount_ttc"])) * quantity
    ht = ttc / (1 + Decimal(line["tax_rate"]) / 100)
    cost = (
        None
        if line["unit_cost_ht"] is None
        else Decimal(line["unit_cost_ht"]) * quantity
    )
    # Tax is the difference of rounded totals so displayed components reconcile.
    rounded_ht = Decimal(amount(ht))
    return {
        "total_ttc": amount(ttc),
        "total_ht": amount(rounded_ht),
        "tax": amount(ttc - rounded_ht),
        "contribution_ht": None if cost is None else amount(rounded_ht - cost),
    }


def document(db, identity):
    row = db.execute(
        "SELECT d.*,sd.sold_on,c.name customer_name FROM commercial_documents d LEFT JOIN commercial_sale_dates sd ON sd.document_id=d.id LEFT JOIN crm_contacts c ON c.id=d.customer_id WHERE d.id=?",
        (identity,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Document commercial introuvable.")
    result = dict(row)
    lines = [
        dict(r)
        for r in db.execute(
            "SELECT l.*,COALESCE((SELECT SUM(r.quantity) FROM commercial_returns r WHERE r.line_id=l.id),0) returned,COALESCE((SELECT SUM(r.quantity) FROM commercial_returns r WHERE r.line_id=l.id AND r.restock=1),0) restocked FROM commercial_lines l WHERE document_id=? ORDER BY l.id",
            (identity,),
        )
    ]
    for line in lines:
        line.update(line_totals(line))
        line["net"] = line_totals(line, line["quantity"] - line["returned"])
        if line["unit_cost_ht"] is not None:
            line["net"]["contribution_ht"] = amount(
                Decimal(line["net"]["total_ht"])
                - Decimal(line["unit_cost_ht"]) * (line["quantity"] - line["restocked"])
            )
    result["lines"] = lines
    result["returns"] = [
        dict(r)
        for r in db.execute(
            "SELECT r.* FROM commercial_returns r JOIN commercial_lines l ON l.id=r.line_id WHERE l.document_id=? ORDER BY r.id DESC",
            (identity,),
        )
    ]
    result["totals"] = {
        key: amount(sum((Decimal(line[key]) for line in lines), Decimal(0)))
        for key in ("total_ttc", "total_ht", "tax")
    }
    result["totals"]["contribution_ht"] = (
        None
        if any(l["contribution_ht"] is None for l in lines)
        else amount(sum((Decimal(l["contribution_ht"]) for l in lines), Decimal(0)))
    )
    result["net_total_ttc"] = amount(
        sum((Decimal(l["net"]["total_ttc"]) for l in lines), Decimal(0))
    )
    return result


def stock_change(db, product_id, delta, actor, reason, expected_version):
    item = product(db, product_id)
    check_version(item, expected_version)
    before = item["current_stock"]
    after = before + delta
    if after < 0:
        raise HTTPException(409, f"Stock insuffisant pour {item['sku']}.")
    if after > 2147483647:
        raise HTTPException(422, "Stock maximum dépassé.")
    stamp = now()
    db.execute(
        "INSERT INTO movements(product_id,type,quantity,reason,stock_before,stock_after,created_at,actor_id) VALUES (?,?,?,?,?,?,?,?)",
        (
            product_id,
            "IN" if delta > 0 else "OUT",
            abs(delta),
            reason,
            before,
            after,
            stamp,
            actor,
        ),
    )
    db.execute(
        "UPDATE products SET current_stock=?,version=version+1,updated_at=? WHERE id=?",
        (after, stamp, product_id),
    )
