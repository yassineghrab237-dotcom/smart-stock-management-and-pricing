"""Analyse descriptive des ventes confirmées et retours connus (cohorte de ventes)."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import combinations
from services.stock_service.app.services.commerce import amount, line_totals

TUNIS = timezone(timedelta(hours=1))


def business_day(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(TUNIS).date()


def report(db, start, end, customer_id=None):
    # Returns are attributed to their original sale, including returns after end.
    # This is a sales-cohort view, not a period accounting ledger.
    docs = {
        r["id"]: dict(r)
        for r in db.execute(
            "SELECT d.*,sd.sold_on,c.name customer_name FROM commercial_documents d LEFT JOIN commercial_sale_dates sd ON sd.document_id=d.id LEFT JOIN crm_contacts c ON c.id=d.customer_id WHERE d.kind='SALE' AND d.status='CONFIRMED'"
        )
        if start
        <= (
            date.fromisoformat(r["sold_on"])
            if r["sold_on"]
            else business_day(r["confirmed_at"])
        )
        <= end
        and (customer_id is None or r["customer_id"] == customer_id)
    }
    products = {
        r["id"]: dict(r)
        for r in db.execute("SELECT id,sku,name,current_stock FROM products")
    }
    results, baskets, sales = {}, defaultdict(set), {}
    for identity, doc in docs.items():
        sales[identity] = dict(
            id=identity,
            reference=doc["reference"],
            customer_name=doc["customer_name"],
            sold_on=doc["sold_on"] or business_day(doc["confirmed_at"]).isoformat(),
            net_ttc=Decimal(0),
        )
    rows = db.execute(
        """SELECT l.*,COALESCE(r.returned,0) returned,COALESCE(r.restocked,0) restocked FROM commercial_lines l
        LEFT JOIN (SELECT line_id,SUM(quantity) returned,SUM(CASE WHEN restock=1 THEN quantity ELSE 0 END) restocked FROM commercial_returns GROUP BY line_id) r ON r.line_id=l.id
        JOIN commercial_documents d ON d.id=l.document_id WHERE d.kind='SALE' AND d.status='CONFIRMED'"""
    )
    total = dict(
        net_ttc=Decimal(0),
        net_ht=Decimal(0),
        known_contribution_ht=Decimal(0),
        sold_units=0,
        returned_units=0,
        known_cost_lines=0,
        line_count=0,
    )
    for row in rows:
        line = dict(row)
        if line["document_id"] not in docs:
            continue
        pid = line["product_id"]
        if pid not in results:
            results[pid] = {
                **products[pid],
                **{
                    k: Decimal(0) if isinstance(v, Decimal) else 0
                    for k, v in total.items()
                },
                "baskets": 0,
            }
        item = results[pid]
        net_qty = line["quantity"] - line["returned"]
        net = line_totals(line, net_qty)
        contribution = (
            None
            if line["unit_cost_ht"] is None
            else Decimal(net["total_ht"])
            - Decimal(line["unit_cost_ht"]) * (line["quantity"] - line["restocked"])
        )
        for bucket in [total, item]:
            bucket["net_ttc"] += Decimal(net["total_ttc"])
            bucket["net_ht"] += Decimal(net["total_ht"])
            bucket["sold_units"] += line["quantity"]
            bucket["returned_units"] += line["returned"]
            bucket["line_count"] += 1
            if contribution is not None:
                bucket["known_cost_lines"] += 1
                bucket["known_contribution_ht"] += contribution
        sales[line["document_id"]]["net_ttc"] += Decimal(net["total_ttc"])
        if net_qty > 0:
            baskets[line["document_id"]].add(pid)
    occurrences, pairs = Counter(), Counter()
    for items in baskets.values():
        occurrences.update(items)
        pairs.update(combinations(sorted(items), 2))
    for pid, item in results.items():
        item["baskets"] = occurrences[pid]

    def serialize(bucket):
        bucket["net_units"] = bucket["sold_units"] - bucket["returned_units"]
        bucket["contribution_ht"] = (
            amount(bucket["known_contribution_ht"])
            if bucket["line_count"] == bucket["known_cost_lines"]
            else None
        )
        return {
            k: amount(v) if isinstance(v, Decimal) else v for k, v in bucket.items()
        }

    items = [serialize(v) for v in results.values()]
    items.sort(
        key=lambda v: (
            v["contribution_ht"] is not None,
            Decimal(v["contribution_ht"] or "0"),
            Decimal(v["net_ht"]),
        ),
        reverse=True,
    )
    associations = [
        dict(
            product_a=products[a]["sku"],
            product_b=products[b]["sku"],
            baskets=n,
            total_baskets=len(baskets),
            a_baskets=occurrences[a],
            b_baskets=occurrences[b],
        )
        for (a, b), n in pairs.most_common(20)
        if n >= 2
    ]
    recent = sorted(
        sales.values(), key=lambda s: (s["sold_on"], s["id"]), reverse=True
    )[:30]
    return dict(
        start=start.isoformat(),
        end=end.isoformat(),
        as_of=datetime.now(TUNIS).isoformat(),
        currency="TND",
        sales_count=len(docs),
        active_baskets=len(baskets),
        totals=serialize(total),
        products=items,
        associations=associations,
        sales=[{**s, "net_ttc": amount(s["net_ttc"])} for s in recent],
    )
