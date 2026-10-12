from datetime import date, timedelta
import hashlib
import json
import sqlite3

from services.stock_service.app.services import demand_model as model
from services.stock_service.app.services.analysis import evaluate, snapshot
from test_imports import client


def test_final_test_values_never_change_tuning():
    first = model.forecast([20, 50, 80] * 12)
    second = model.forecast(([20, 50, 80] * 12)[:-4] + [999, 1, 888, 2])
    assert first["tuning"]["tuned"]
    assert first["selected_parameters"] == second["selected_parameters"]
    assert first["tuning"] == second["tuning"]
    assert first["model_mae"] != second["model_mae"]


def test_tuning_fits_only_past_targets(monkeypatch):
    calls = []
    original = model.fit_model

    def recording(x, y, params):
        calls.append(list(y))
        return original(x, y, params)

    monkeypatch.setattr(model, "fit_model", recording)
    model.select_parameters([[i] * 8 for i in range(16)], list(range(16)))
    assert len(calls) == 6  # trois configurations, deux plis
    assert calls == [list(range(8)), list(range(12))] * 3


def test_short_history_has_no_parameter_search():
    result = model.forecast([20, 50, 80, 30] * 4)
    assert result["tuning"] == {"tuned": False, "tuning_folds": 0, "candidates": []}
    assert result["selected_parameters"] == model.DEFAULT


def test_marginal_validation_gain_does_not_replace_defaults(monkeypatch):
    class ConstantPrediction:
        def __init__(self, value):
            self.value = value

        def predict(self, x):
            return [self.value] * len(x)

    def fit(x, y, params):
        return ConstantPrediction(98 if params["n_estimators"] == 50 else 97.95)

    monkeypatch.setattr(model, "fit_model", fit)
    params, _ = model.select_parameters([[i] * 8 for i in range(16)], [100] * 16)
    assert params == model.DEFAULT


def test_simple_cycle_beats_unnecessary_ml():
    result = model.forecast([20, 80] * 12)
    assert result["baseline_errors"]["last_week"] == 60
    assert result["baseline_errors"]["repeat_four_weeks"] == 0
    assert result["status"] == "unavailable" and result["prediction"] is None


def test_nonlinear_cycle_can_beat_all_three_baselines():
    result = model.forecast([20, 50, 80] * 8)
    assert result["status"] == "available"
    assert result["model_mae"] < min(result["baseline_errors"].values())
    assert 0 <= result["prediction"] <= 100


def test_partial_current_week_not_used():
    as_of = date(2026, 10, 12)
    sales = [
        {
            "sold_on": (as_of - timedelta(weeks=24 - i)).isoformat(),
            "quantity": [20, 50, 80][i % 3],
        }
        for i in range(24)
    ]
    product = {"id": 1, "sku": "QA", "name": "QA"}
    previous = evaluate(product, sales, as_of)
    assert (
        evaluate(
            product, sales + [{"sold_on": as_of.isoformat(), "quantity": 99999}], as_of
        )
        == previous
    )


def test_algorithm_upgrade_invalidates_old_job_without_removing_it(client):
    with sqlite3.connect(client.app.state.db_path) as db:
        db.row_factory = sqlite3.Row
        source, new_fingerprint = snapshot(db)
        source.pop("algorithm_version")
        old = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
        assert old != new_fingerprint
        db.execute(
            "INSERT INTO analysis_jobs(fingerprint,status,progress,message,actor_id,created_at,updated_at) VALUES (?,'SUCCEEDED',100,'QA ancien',1,'2026-01-01','2026-01-01')",
            (old,),
        )
    assert client.get("/api/analysis/jobs").json()["items"][0]["stale"] is True
    started = client.post("/api/analysis/jobs").json()
    assert started["fingerprint"] == new_fingerprint
    assert len(client.get("/api/analysis/jobs").json()["items"]) == 2
