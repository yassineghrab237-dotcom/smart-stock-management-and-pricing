"""Read-only integration of stock products with explicitly linked real ML data."""

import csv
import json
from pathlib import Path


def recommendation(product: dict) -> dict:
    def unavailable(source: str, detail: str) -> dict:
        return {
            "status": "unavailable",
            "source": source,
            "detail": detail,
            "product_id": product.get("id", product.get("product_id")),
        }

    # SQLite IDs alone are unrelated to demo CSV identifiers. Require provenance
    # before importing any ML dependency or considering an artifact.
    if product.get("ml_data_source") != "real" or not product.get("ml_dataset_path"):
        return unavailable(
            "UNLINKED_DATA",
            "Aucun historique réel explicitement lié à ce produit; les CSV de démonstration ne sont pas utilisés.",
        )
    try:
        from services.ml_inference_service.app.core.config import (
            DATA_DIR,
            MODELS_DIR,
            REPORTS_DIR,
        )

        if Path(product["ml_dataset_path"]).resolve() != DATA_DIR:
            return unavailable(
                "DATASET_MISMATCH",
                "Le produit et le service ML ne référencent pas le même jeu de données.",
            )
        metadata = json.loads((DATA_DIR / "config.json").read_text(encoding="utf-8"))
        if metadata.get("data_source") != "real":
            return unavailable(
                "DEMO_OR_UNKNOWN_DATA",
                "La provenance du jeu de données n'est pas déclarée réelle.",
            )
        csv_id = product.get("ml_product_id")
        if csv_id is None or not product.get("sku"):
            return unavailable(
                "IDENTITY_MISSING", "Identifiant ML et SKU explicitement liés requis."
            )
        with (DATA_DIR / "products.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if row.get("product_id") == str(csv_id)
                and row.get("sku") == str(product["sku"])
            ]
        if len(rows) != 1:
            return unavailable(
                "IDENTITY_MISMATCH",
                "Aucune identité produit unique correspondant au SKU et à l'identifiant liés.",
            )
        # Local stock and pricing values must also agree; never silently infer
        # against stale product attributes from another system.
        csv_product = rows[0]
        for field in ("current_price", "cost_price", "current_stock"):
            if field not in product or float(product[field]) != float(
                csv_product[field]
            ):
                return unavailable(
                    "STALE_DATA",
                    "Les attributs du stock et du jeu de données ML divergent.",
                )
        from services.ml_inference_service.app.services.demand_predictor import (
            DemandPredictor,
        )
        from services.ml_inference_service.app.services.model_store import ModelStore
        from services.ml_inference_service.app.services.price_engine import (
            PriceMLRecommender,
        )
        import pandas as pd

        store = ModelStore(MODELS_DIR)
        demand = DemandPredictor(DATA_DIR, MODELS_DIR).predict_weekly(int(csv_id))
        if demand.get("source") not in ("ML_QUANTILE_GBR", "BASELINE"):
            return unavailable(
                demand.get("source", "NO_DATA"),
                demand.get("explanation", "Prévision indisponible."),
            )
        price = PriceMLRecommender(store, REPORTS_DIR).recommend_price_ml(
            csv_product,
            pd.read_csv(DATA_DIR / "sales.csv"),
            pd.read_csv(DATA_DIR / "competitor_prices.csv"),
            pd.read_csv(DATA_DIR / "promotions.csv"),
        )
        return {
            "status": "available",
            "source": "REAL_LINKED_LOCAL_MODEL",
            "product_id": product.get("id"),
            "demand": demand,
            "price": price,
            "detail": "Estimation locale non validée sur données hors entraînement; aucune application automatique.",
        }
    except (FileNotFoundError, ValueError, KeyError, ImportError, OSError) as exc:
        return unavailable(
            "MODEL_OR_DATA_UNAVAILABLE",
            f"Modèle ou données indisponibles ({type(exc).__name__}); aucun prix inventé.",
        )
    except Exception:
        return unavailable(
            "INFERENCE_ERROR",
            "Calcul ML indisponible; aucune recommandation appliquée.",
        )
