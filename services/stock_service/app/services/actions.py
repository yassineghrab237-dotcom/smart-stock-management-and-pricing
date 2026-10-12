"""Conditions présentes et décisions humaines ; acquitter ne résout pas la cause."""

import hashlib, json
from datetime import datetime, timedelta, timezone
from libs.common.database import now


def actions(db):
    items = []
    today = datetime.now(timezone(timedelta(hours=1))).date().isoformat()

    def add(kind, identity, condition, title, detail, page, priority):
        key = hashlib.sha256(
            json.dumps(
                [kind, identity, condition], sort_keys=True, default=str
            ).encode()
        ).hexdigest()
        items.append(
            dict(
                key=key,
                kind=kind,
                identity=identity,
                title=title,
                detail=detail,
                page=page,
                priority=priority,
                status="TODO",
                decision=None,
            )
        )

    for p in db.execute("SELECT * FROM products"):
        if p["current_stock"] <= p["threshold_min"]:
            add(
                "STOCK",
                p["id"],
                [p["current_stock"], p["threshold_min"]],
                p["name"],
                f"{p['sku']} : {p['current_stock']} unités, seuil {p['threshold_min']}. Vérifiez les engagements et la proposition de réassort.",
                "replenishment",
                1 if p["current_stock"] == 0 else 2,
            )
        elif p["threshold_max"] is not None and p["current_stock"] > p["threshold_max"]:
            add(
                "OVERSTOCK",
                p["id"],
                [p["current_stock"], p["threshold_max"]],
                p["name"],
                f"{p['current_stock']} unités au-delà du maximum {p['threshold_max']}. Contrôlez les ventes et achats engagés.",
                "insights",
                3,
            )
    for p in db.execute(
        "SELECT p.*,c.name supplier FROM purchase_orders_local p JOIN crm_contacts c ON c.id=p.supplier_id WHERE p.status IN ('ORDERED','PART_RECEIVED') AND p.expected_on<?",
        (today,),
    ):
        add(
            "LATE_PURCHASE",
            p["id"],
            [p["version"], p["expected_on"]],
            f"Réception en retard · {p['reference']}",
            f"{p['supplier']} · attendue le {p['expected_on']}. Solde fournisseur à contrôler.",
            "purchases",
            1,
        )
    for t in db.execute(
        "SELECT t.*,c.name contact FROM crm_tasks t JOIN crm_contacts c ON c.id=t.contact_id WHERE t.status='TODO' AND t.due_on<=?",
        (today,),
    ):
        add(
            "CRM_TASK",
            t["id"],
            t["version"],
            t["title"],
            f"{t['contact']} · échéance {t['due_on']}.",
            "crm",
            2,
        )
    for o in db.execute(
        "SELECT o.*,c.name contact FROM crm_opportunities o JOIN crm_contacts c ON c.id=o.contact_id WHERE o.stage NOT IN ('WON','LOST') AND o.close_on<=?",
        (today,),
    ):
        add(
            "OPPORTUNITY",
            o["id"],
            o["version"],
            o["title"],
            f"{o['contact']} · opportunité à revoir depuis le {o['close_on']}.",
            "crm",
            2,
        )
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    for w in db.execute(
        """SELECT w.*,p.name,j.id job_id,j.status job_status,j.message,j.review_state,j.finished_at FROM collection_watches w JOIN products p ON p.id=w.product_id LEFT JOIN collection_jobs j ON j.id=(SELECT MAX(j2.id) FROM collection_jobs j2 WHERE j2.watch_id=w.id) WHERE w.enabled=1"""
    ):
        if not w["job_id"] or w["job_status"] in ("FAILED", "BLOCKED", "INTERRUPTED"):
            add(
                "COLLECTION",
                w["id"],
                [w["job_id"], w["job_status"]],
                f"Veille à vérifier · {w['name']}",
                f"{w['retailer']} · {w['message'] or 'Aucune collecte exécutée.'}",
                "market",
                2,
            )
        elif w["job_status"] == "SUCCEEDED" and w["review_state"] == "PENDING":
            add(
                "MATCHING",
                w["id"],
                w["job_id"],
                f"Offre à valider · {w['name']}",
                f"{w['retailer']} · confirmez l’identité et la variante avant comparaison.",
                "market",
                2,
            )
    for o in db.execute(
        """SELECT o.*,p.name FROM market_observations o JOIN products p ON p.id=o.product_id WHERE o.id=(SELECT x.id FROM market_observations x WHERE x.product_id=o.product_id AND x.source_url=o.source_url ORDER BY x.observed_at DESC,x.id DESC LIMIT 1) AND o.observed_at<?""",
        (cutoff,),
    ):
        add(
            "STALE_PRICE",
            o["id"],
            o["observed_at"],
            f"Prix périmé · {o['name']}",
            f"{o['retailer']} · relevé de plus de 24 h ; exclu des comparaisons courantes.",
            "market",
            3,
        )
    decisions = {
        r["action_key"]: dict(r)
        for r in db.execute(
            "SELECT * FROM decision_events WHERE id IN (SELECT MAX(id) FROM decision_events GROUP BY action_key)"
        )
    }
    for item in items:
        if item["key"] in decisions:
            item.update(
                status=decisions[item["key"]]["status"], decision=decisions[item["key"]]
            )
    items.sort(key=lambda x: (x["status"] == "ACKNOWLEDGED", x["priority"], x["title"]))
    return items
