"""Prévisions sur ventes importées ; évaluation chronologique et baseline."""

import hashlib
import json
import math
from collections import defaultdict
from datetime import date, timedelta

from libs.common.database import connect, now


def snapshot(db):
    products = [
        dict(r) for r in db.execute("SELECT id,sku,name FROM products ORDER BY id")
    ]
    sales = [
        dict(r)
        for r in db.execute(
            "SELECT reference,product_id,sold_on,quantity FROM sales_history ORDER BY product_id,sold_on,reference"
        )
    ]
    source = {"products": products, "sales": sales, "as_of": date.today().isoformat()}
    fingerprint = hashlib.sha256(
        json.dumps(source, sort_keys=True).encode()
    ).hexdigest()
    return source, fingerprint


def update(path, job_id, status, progress, message, result=None):
    with connect(path, write=True) as db:
        db.execute(
            "UPDATE analysis_jobs SET status=?,progress=?,message=?,result=?,updated_at=? WHERE id=?",
            (
                status,
                progress,
                message,
                json.dumps(result) if result is not None else None,
                now(),
                job_id,
            ),
        )


def evaluate(product, sales, as_of):
    from sklearn.ensemble import GradientBoostingRegressor

    weeks = defaultdict(int)
    current_week = as_of - timedelta(days=as_of.weekday())
    for sale in sales:
        sold = date.fromisoformat(sale["sold_on"])
        week = sold - timedelta(days=sold.weekday())
        if week < current_week:
            weeks[week] += sale["quantity"]
    result = {
        "product_id": product["id"],
        "sku": product["sku"],
        "name": product["name"],
        "status": "unavailable",
        "prediction": None,
        "weeks": len(weeks),
    }
    ordered = sorted(weeks)
    if len(ordered) < 16:
        return {
            **result,
            "detail": "Au moins 16 semaines terminées avec ventes sont nécessaires ; importez un historique plus long.",
        }
    if any(b - a != timedelta(days=7) for a, b in zip(ordered, ordered[1:])):
        return {
            **result,
            "detail": "Des semaines manquent. Aucun zéro de vente n'est inventé ; complétez ou vérifiez la couverture de l'historique.",
        }
    if ordered[-1] != current_week - timedelta(days=7):
        return {
            **result,
            "detail": "Historique ancien : la dernière semaine terminée manque. Aucune prévision actuelle présentée.",
        }
    quantities = [weeks[w] for w in ordered]
    features = [quantities[i - 4 : i] for i in range(4, len(quantities))]
    targets = quantities[4:]
    # Les quatre dernières semaines servent uniquement à l'évaluation.
    model = GradientBoostingRegressor(n_estimators=100, max_depth=2, random_state=42)
    model.fit(features[:-4], targets[:-4])
    estimates = model.predict(features[-4:])
    mae = sum(abs(float(p) - actual) for p, actual in zip(estimates, targets[-4:])) / 4
    baseline_mae = (
        sum(abs(x[-1] - actual) for x, actual in zip(features[-4:], targets[-4:])) / 4
    )
    metrics = {
        "model_mae": round(mae, 4),
        "baseline_mae": round(baseline_mae, 4),
        "evaluation_weeks": 4,
        "training_weeks": len(features) - 4,
    }
    if not math.isfinite(mae) or mae >= baseline_mae:
        return {
            **result,
            **metrics,
            "detail": "Sur les 4 semaines de contrôle, le modèle ne fait pas mieux que la dernière semaine connue. Prévision masquée.",
        }
    model.fit(features, targets)
    prediction = max(0, float(model.predict([quantities[-4:]])[0]))
    return {
        **result,
        **metrics,
        "status": "available",
        "prediction": round(prediction, 2),
        "target_week": current_week.isoformat(),
        "detail": "Estimation de demande, avec erreur mesurée sur 4 semaines passées. À vérifier avant décision ; aucun stock ou prix modifié.",
    }


def run_analysis(path, job_id, source):
    try:
        update(path, job_id, "RUNNING", 5, "Lecture et contrôle des ventes importées.")
        by_product = defaultdict(list)
        for sale in source["sales"]:
            by_product[sale["product_id"]].append(sale)
        results = []
        products = source["products"]
        for index, product in enumerate(products):
            results.append(
                evaluate(
                    product,
                    by_product[product["id"]],
                    date.fromisoformat(source["as_of"]),
                )
            )
            update(
                path,
                job_id,
                "RUNNING",
                5 + int(90 * (index + 1) / max(1, len(products))),
                f"{index+1}/{len(products)} produits évalués.",
            )
        update(
            path,
            job_id,
            "SUCCEEDED",
            100,
            "Analyse terminée. Consultez les résultats et les limites par produit.",
            {
                "products": results,
                "source": "USER_IMPORTED_HISTORY",
                "data_authenticity": "not_verified",
                "method": "GradientBoostingRegressor ; contrôle chronologique contre dernière semaine",
                "as_of": source["as_of"],
            },
        )
    except Exception:
        update(
            path,
            job_id,
            "FAILED",
            100,
            "Le calcul a échoué. Vérifiez les données et relancez l'analyse ; aucun stock ni prix modifié.",
        )
