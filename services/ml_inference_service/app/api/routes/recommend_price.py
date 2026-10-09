from fastapi import APIRouter, HTTPException
import pandas as pd

from ...core.config import DATA_DIR, MODELS_DIR, REPORTS_DIR
from ...services.model_store import ModelStore
from ...services.price_engine import PriceMLRecommender

router = APIRouter(prefix="/recommend")
store = ModelStore(MODELS_DIR)
engine = PriceMLRecommender(store=store, reports_dir=REPORTS_DIR)


@router.get("/price/{product_id}")
def recommend_price(product_id: int):
    try:
        products = pd.read_csv(DATA_DIR / "products.csv")
        competitor_prices = pd.read_csv(DATA_DIR / "competitor_prices.csv")
        sales = pd.read_csv(DATA_DIR / "sales.csv")
        promotions = pd.read_csv(DATA_DIR / "promotions.csv")

        prod_row = products[products["product_id"] == product_id]
        if prod_row.empty:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        return engine.recommend_price_ml(
            product=prod_row.iloc[0].to_dict(),
            sales=sales,
            competitor_prices=competitor_prices,
            promotions=promotions,
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Données ou modèles locaux absents; recommandation indisponible.",
        )
    except ValueError:
        raise HTTPException(
            status_code=503,
            detail="Modèle non utilisable ou historique insuffisant; recommandation indisponible.",
        )
    except Exception:
        raise HTTPException(
            status_code=500, detail="Erreur de calcul ML; aucun résultat disponible."
        )
