"""Réglage borné, uniquement sur le passé ; contrôle final séparé."""

import math
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit

ALGORITHM_VERSION = "demand-v2-temporal-tuning"
DEFAULT = {"n_estimators": 100, "max_depth": 2, "min_samples_leaf": 1}
CANDIDATES = (
    {"n_estimators": 50, "max_depth": 1, "min_samples_leaf": 2},
    DEFAULT,
    {"n_estimators": 100, "max_depth": 2, "min_samples_leaf": 3},
)
BASELINES = {
    "last_week": "dernière semaine",
    "mean_four_weeks": "moyenne des quatre dernières semaines",
    "repeat_four_weeks": "répétition du niveau quatre semaines auparavant",
}


def features(history):
    recent = history[-4:]
    # Toutes ces valeurs sont connues avant la semaine à prédire.
    return [*recent, sum(recent) / 4, min(recent), max(recent), recent[-1] - recent[0]]


def fit_model(x, y, params):
    return GradientBoostingRegressor(
        **params, learning_rate=0.1, random_state=42, loss="squared_error"
    ).fit(x, y)


def mae(actual, predicted):
    return sum(abs(a - max(0, float(p))) for a, p in zip(actual, predicted)) / len(
        actual
    )


def select_parameters(x, y):
    # 24 semaines brutes => 16 exemples avant le contrôle final.
    # Premier pli : >= 8 exemples d'entraînement ; validation sur 4 semaines.
    if len(y) < 16:
        return dict(DEFAULT), {"tuned": False, "tuning_folds": 0, "candidates": []}
    folds = list(TimeSeriesSplit(n_splits=2, test_size=4).split(x))
    scores = []
    for params in CANDIDATES:
        errors = []
        for train, validation in folds:
            model = fit_model([x[i] for i in train], [y[i] for i in train], params)
            errors.append(
                mae(
                    [y[i] for i in validation],
                    model.predict([x[i] for i in validation]),
                )
            )
        scores.append(
            {"parameters": dict(params), "validation_mae": sum(errors) / len(errors)}
        )
    best = min(scores, key=lambda item: item["validation_mae"])
    default_score = next(item for item in scores if item["parameters"] == DEFAULT)
    # Seuil de stabilité heuristique : ne pas changer pour un gain marginal.
    # Ce n'est ni un intervalle de confiance ni une garantie de gain futur.
    if best["validation_mae"] >= default_score["validation_mae"] * 0.95:
        best = default_score
    return best["parameters"], {"tuned": True, "tuning_folds": 2, "candidates": scores}


def forecast(quantities):
    x = [features(quantities[i - 4 : i]) for i in range(4, len(quantities))]
    y = quantities[4:]
    # Ne transmettre NI les cibles NI les features finales au réglage.
    params, tuning = select_parameters(x[:-4], y[:-4])
    model = fit_model(x[:-4], y[:-4], params)
    model_error = mae(y[-4:], model.predict(x[-4:]))
    baseline_predictions = {
        "last_week": [row[3] for row in x[-4:]],
        "mean_four_weeks": [row[4] for row in x[-4:]],
        "repeat_four_weeks": [row[0] for row in x[-4:]],
    }
    baseline_errors = {
        key: mae(y[-4:], values) for key, values in baseline_predictions.items()
    }
    best_baseline = min(baseline_errors, key=baseline_errors.get)
    baseline_error = baseline_errors[best_baseline]
    metrics = {
        "algorithm_version": ALGORITHM_VERSION,
        "model_mae": round(model_error, 4),
        "baseline_mae": round(baseline_error, 4),
        "baseline_name": BASELINES[best_baseline],
        "baseline_errors": {
            key: round(value, 4) for key, value in baseline_errors.items()
        },
        "evaluation_weeks": 4,
        "training_weeks": len(y) - 4,
        "selected_parameters": params,
        "tuning": tuning,
    }
    # Comparaison conservatrice à la meilleure des trois méthodes de contrôle.
    if not math.isfinite(model_error) or model_error >= baseline_error:
        return {
            **metrics,
            "status": "unavailable",
            "prediction": None,
            "detail": "Sur les 4 semaines de contrôle final, le modèle ne fait pas mieux que la meilleure des trois méthodes simples. Prévision masquée.",
        }
    # Réentraînement final seulement après l'évaluation, sans changer les réglages.
    model = fit_model(x, y, params)
    prediction = max(0, float(model.predict([features(quantities)])[0]))
    if not math.isfinite(prediction):
        return {
            **metrics,
            "status": "unavailable",
            "prediction": None,
            "detail": "Calcul non exploitable. Prévision masquée.",
        }
    return {
        **metrics,
        "status": "available",
        "prediction": round(prediction, 2),
        "detail": "Estimation contrôlée sur 4 semaines séparées du réglage. Le modèle fait mieux que les trois méthodes simples sur cette période ; cela ne garantit pas les ventes futures. Aucun stock ni prix modifié.",
    }
