"""ML integration checks with synthetic CSVs and newly generated models only."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def run_worker(directory: Path) -> None:
    import pandas as pd
    from fastapi.testclient import TestClient
    from libs.ml_bridge import recommendation
    from services.ml_training_service.app.core.config import DATA_DIR, MODELS_DIR
    from services.ml_training_service.app.main import app as training
    from services.ml_inference_service.app.main import app as inference
    from services.ml_inference_service.app.services.model_store import ModelStore

    assert DATA_DIR == directory / "data"
    assert not MODELS_DIR.exists(), "Import must not create artifacts"
    train = TestClient(training, client=("127.0.0.1", 50000))
    infer = TestClient(inference, client=("127.0.0.1", 50000))
    assert (
        TestClient(training, client=("192.0.2.1", 50000)).post("/train/all").status_code
        == 403
    )
    assert (
        TestClient(inference, client=("192.0.2.1", 50000)).get("/health").status_code
        == 403
    )
    assert train.get("/health").status_code == 200
    assert (
        train.post(
            "/train/all", headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert (
        train.post(
            "/train/all",
            headers={"Host": "attacker.example", "Origin": "http://attacker.example"},
        ).status_code
        == 400
    )
    assert infer.get("/health").status_code == 200
    assert train.post("/train/all").status_code == 422
    assert infer.get("/predict/demand-weekly/1").status_code == 503
    DATA_DIR.mkdir(parents=True)
    products = []
    sales = []
    competitors = []
    suppliers = []
    for pid in (1, 2):
        products.append(
            dict(
                product_id=pid,
                sku=f"QA-{pid}",
                current_price=20.0,
                cost_price=10.0,
                min_price=12.0,
                min_margin=0.2,
                current_stock=15,
                threshold_min=5,
                threshold_max=40,
            )
        )
        suppliers.append(dict(product_id=pid, is_preferred=True, lead_time_days=7))
        for week in range(12):
            date = pd.Timestamp("2026-01-05") + pd.Timedelta(weeks=week)
            sales.append(
                dict(
                    product_id=pid,
                    timestamp=date.isoformat(),
                    qty=pid + week % 4 + 4,
                    unit_price=20.0,
                )
            )
            competitors.append(
                dict(
                    product_id=pid,
                    competitor_id=1,
                    collected_at=date.isoformat(),
                    competitor_price=19.0 + week % 3,
                    status="OK",
                )
            )
    pd.DataFrame(products).to_csv(DATA_DIR / "products.csv", index=False)
    pd.DataFrame(sales).to_csv(DATA_DIR / "sales.csv", index=False)
    pd.DataFrame(competitors).to_csv(DATA_DIR / "competitor_prices.csv", index=False)
    pd.DataFrame(suppliers).to_csv(DATA_DIR / "product_suppliers.csv", index=False)
    pd.DataFrame(
        columns=["product_id", "start_date", "end_date", "promo_price"]
    ).to_csv(DATA_DIR / "promotions.csv", index=False)
    (DATA_DIR / "config.json").write_text(
        json.dumps({"data_source": "demo"}), encoding="utf-8"
    )
    assert recommendation({"id": 1, "sku": "QA-1"})["source"] == "UNLINKED_DATA"
    assert infer.get("/recommend/price/9999").status_code == 404
    assert infer.get("/recommend/price/1").status_code == 503
    assert infer.get("/predict/demand-weekly/1").json()["source"] == "NO_MODEL"
    for route in ("all", "demand-ml", "price-ml", "anomaly-ml", "promo-ml"):
        response = train.post(f"/train/{route}")
        assert response.status_code == 200, (route, response.text)
    routes = (
        "/predict/demand-weekly/1",
        "/predict/stock-risk/1",
        "/recommend/price/1",
        "/recommend/restock/1",
        "/recommend/promo/1",
        "/detect/anomalies/1",
    )
    for route in routes:
        response = infer.get(route)
        assert response.status_code == 200, (route, response.text)
        assert response.json()["product_id"] == 1
    assert infer.get("/predict/demand-weekly/1").json()["source"] == "ML_QUANTILE_GBR"
    assert infer.get("/predict/stock-risk/9999").status_code == 404
    # Demonstration CSVs remain blocked even with an explicit matching ID/SKU.
    linked = dict(
        products[0],
        id=1,
        ml_data_source="real",
        ml_dataset_path=str(DATA_DIR),
        ml_product_id=1,
    )
    assert recommendation(linked)["source"] == "DEMO_OR_UNKNOWN_DATA"
    (DATA_DIR / "config.json").write_text(
        json.dumps({"data_source": "real"}), encoding="utf-8"
    )
    assert recommendation(dict(linked, sku="WRONG"))["source"] == "IDENTITY_MISMATCH"
    assert recommendation(dict(linked, current_stock=100))["source"] == "STALE_DATA"
    assert (
        recommendation(linked)["status"] == "unavailable"
    )  # demo-trained artifacts cannot serve newly declared real data
    assert train.post("/train/demand-ml").status_code == 200
    assert train.post("/train/price-ml").status_code == 200
    result = recommendation(linked)
    assert result["status"] == "available", result
    # Refuse an unregistered pickle before deserialization (never load it).
    unregistered = MODELS_DIR / "untrusted_20990101_000000.joblib"
    unregistered.write_bytes(b"not-a-trusted-pickle")
    try:
        ModelStore(MODELS_DIR).load_latest("untrusted", "untrusted_")
    except ValueError:
        pass
    else:
        raise AssertionError("Unregistered artifact accepted")
    # New model outputs remain finite and monthly season feature matches next week.
    from services.ml_inference_service.app.services.price_engine import (
        PriceMLRecommender,
    )

    engine = PriceMLRecommender(ModelStore(MODELS_DIR), directory / "reports")
    weekly = engine._build_weekly(pd.DataFrame(sales))
    features = engine._make_features_for_next_week(weekly, 1, 20, 20, 0)
    assert features[0, -1] == 14  # final observed week 13, target week 14
    import numpy as np

    assert np.isclose(features[0, -2], np.std([8, 7, 6, 5], ddof=1))
    print(
        json.dumps(
            {
                "training_routes": 5,
                "inference_routes": 6,
                "data": "synthetic_only",
                "quality_evaluation": "not_performed",
            }
        )
    )


class MLIntegrationTests(unittest.TestCase):
    def test_synthetic_training_inference_and_provenance(self):
        qa_root = ROOT / "runtime" / "qa-ml"
        qa_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="run-", dir=qa_root) as temp:
            directory = Path(temp)
            env = {
                **os.environ,
                "DATA_DIR": str(directory / "data"),
                "MODELS_DIR": str(directory / "models"),
                "REPORTS_DIR": str(directory / "reports"),
                "PYTHONPATH": str(ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker", temp],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"training_routes": 5', result.stdout)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        run_worker(Path(sys.argv[2]))
    else:
        unittest.main()
