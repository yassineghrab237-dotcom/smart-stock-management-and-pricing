# Optimisation de la demande — 12 octobre 2026

Cette évolution améliore le choix des réglages et les contrôles de la prévision. Elle ne garantit pas une meilleure précision sur chaque série et n’optimise pas le temps CPU. Aucune vente réelle n’a servi à la recette.

## Méthode v2

L’entrée conserve les quatre ventes hebdomadaires précédentes et ajoute leur moyenne, minimum, maximum et variation entre la première et la dernière. Ces valeurs sont connues avant la semaine visée ; aucun chiffre futur n’entre dans les caractéristiques.

À partir de 24 semaines consécutives, trois configurations bornées sont comparées sur deux fenêtres temporelles de quatre semaines. L’entraînement s’étend avec le temps ; il ne mélange pas les dates. Le contrôle final porte sur quatre autres semaines, exclues du réglage. Les prédictions de contrôle sont des prévisions à un pas utilisant les ventes précédentes effectivement observées, pas une simulation de quatre semaines futures sans nouvelles observations.

Configurations : 50 arbres de profondeur 1 et au moins 2 exemples par feuille ; 100 arbres de profondeur 2 et au moins 1 exemple par feuille (réglage initial) ; 100 arbres de profondeur 2 et au moins 3 exemples par feuille. Le taux d’apprentissage reste à 0,1. Pour éviter un changement sur un faible écart, les réglages initiaux sont conservés sauf gain de validation supérieur à 5 %. C’est une règle de stabilité heuristique, pas une preuve statistique. De 16 à 23 semaines, les réglages restent fixes.

Le modèle doit battre **chacune** de ces références sur le contrôle final : dernière semaine, moyenne des quatre dernières semaines, niveau quatre semaines auparavant. La meilleure référence est affichée. Il n’est pas forcé de présenter une prévision quand une méthode simple fait mieux. Le test final sert à accepter ou masquer une prévision, jamais à choisir ses paramètres. Le modèle accepté est ensuite réentraîné sur tout l’historique disponible avec les mêmes paramètres.

Les résultats enregistrent la version d’algorithme, les paramètres sélectionnés, les scores de réglage et les erreurs des trois références. La version entre dans l’empreinte du job : les anciens résultats restent conservés, sont signalés périmés et n’empêchent pas un nouveau calcul. Le contrat de résultat existant et les droits web/mobile sont conservés. Aucun schéma, stock ou prix modifié.

## Mesures reproductibles

Commande : `.venv-local/Scripts/python.exe tests/benchmark_demand.py`.
Résultat : [demand-benchmark.json](evidence/demand-benchmark.json), huit séries synthétiques déterministes. Erreur absolue moyenne en unités sur quatre semaines, plus faible = meilleur :

| Série synthétique | Modèle initial | Modèle v2 | Observation |
|---|---:|---:|---|
| Constante | 0 | 0 | La référence est parfaite ; prévision ML masquée |
| Cycle de 2 semaines | 0,0008 | 0,0008 | Désormais masquée : répétition à quatre semaines parfaite |
| Cycle de 3 semaines | 0,0006 | 0,0006 | Prévision affichée |
| Cycle de 4 semaines | 0,0006 | 0,0006 | Désormais masquée : répétition à quatre semaines parfaite |
| Hausse linéaire | 7,5612 | 7,5612 | Masquée, référence meilleure |
| Bruit | 29,0431 | 16,1982 | Gain, mais prévision toujours masquée : référence à 10,5 |
| Cycle bruité | 3,9686 | 4,4168 | Régression mesurée ; le gain n’est pas universel |
| Changement de régime | 32,4239 | 29,1499 | Gain sur cet exemple uniquement |

Les temps de calcul sont enregistrés par scénario et dépendent de la machine. La recherche implique jusqu’à six ajustements supplémentaires par produit. Ces exemples ont également servi au développement de la règle de stabilité : ils constituent un contrôle de régression transparent, pas un benchmark indépendant ni une estimation de gain métier. Il faut évaluer sur un historique réel autorisé, avec périodes séparées, avant de promettre une amélioration générale.

## Fichiers et validation

- `services/stock_service/app/services/demand_model.py` : caractéristiques, réglage et contrôle final.
- `analysis.py` : intégration aux jobs et empreinte versionnée.
- `tests/test_demand_model.py` : indépendance des données finales, limites temporelles des entraînements, historique court, références, semaine partielle et invalidation des anciens jobs.
- `frontend/src/features/analysis/AnalysisPage.tsx` : explications et comparaison lisibles.
- `tests/browser-delivery.mjs` : recette HTTP/UI, dont absence d’écriture de stock et résultats périmés masqués.

Références : [validation temporelle scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html), [GradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingRegressor.html).
