"""Comparaison reproductible, uniquement synthétique ; aucune base ouverte."""

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sklearn.ensemble import GradientBoostingRegressor
from services.stock_service.app.services.demand_model import forecast


def benchmark():
    rng = random.Random(42)
    cases = {
        "constant": [40] * 52,
        "cycle_2": [20, 80] * 26,
        "cycle_3": [20, 50, 80] * 18,
        "cycle_4": [15, 80, 35, 60] * 13,
        "hausse_lineaire": [20 + i * 3 for i in range(52)],
        "bruit": [rng.randint(20, 80) for _ in range(52)],
        "cycle_bruite": [
            max(1, [20, 50, 80][i % 3] + rng.randint(-8, 8)) for i in range(54)
        ],
        "changement_regime": [20, 50, 80] * 16 + [100, 130, 160, 100, 130, 160],
    }
    results = []
    for name, quantities in cases.items():
        x = [quantities[i - 4 : i] for i in range(4, len(quantities))]
        y = quantities[4:]
        start = perf_counter()
        old = GradientBoostingRegressor(
            n_estimators=100, max_depth=2, random_state=42
        ).fit(x[:-4], y[:-4])
        old_error = (
            sum(abs(float(p) - a) for p, a in zip(old.predict(x[-4:]), y[-4:])) / 4
        )
        old_baseline = sum(abs(row[-1] - a) for row, a in zip(x[-4:], y[-4:])) / 4
        if old_error < old_baseline:
            old.fit(x, y)
            old.predict([quantities[-4:]])
        old_time = perf_counter() - start
        start = perf_counter()
        new = forecast(quantities)
        new_time = perf_counter() - start
        results.append(
            {
                "scenario": name,
                "weeks": len(quantities),
                "old_model_mae": round(old_error, 4),
                "new_model_mae": new["model_mae"],
                "old_forecast_shown": old_error < old_baseline,
                "new_forecast_shown": new["status"] == "available",
                "best_simple_mae": new["baseline_mae"],
                "selected_parameters": new["selected_parameters"],
                "old_seconds": round(old_time, 4),
                "new_seconds": round(new_time, 4),
            }
        )
    report = {
        "date": datetime.now(timezone.utc).isoformat(),
        "scope": "SYNTHETIC_ONLY - final holdout four weeks; tuning on earlier data. No proof of accuracy on real sales.",
        "results": results,
    }
    (ROOT / "docs/evidence/demand-benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    benchmark()
