# Precios — gestion commerciale, stock et veille

Application locale pour une boutique informatique tunisienne, en TND : parcours particuliers et entreprises, saisie et imports CSV. Le web React/TypeScript, le client Flutter et les tâches Python partagent le cœur FastAPI/SQLite.

## Démarrer la recette

```powershell
.\scripts\run-recipe.ps1
```

La recette dispose d'une base distincte, de données fictives et d'un compte généré. Le chemin du fichier d'accès est affiché au lancement. `-New` crée une nouvelle recette sans écraser les précédentes. Ouvrir http://127.0.0.1:8000 ; arrêter avec Ctrl+C. Ne pas saisir de données réelles dans la recette.

[Scénarios et résultats attendus](docs/RECETTE_UTILISATEUR.md) · [État vérifié et limites](docs/PROJECT_STATE.md) · [Carte du code](docs/PROJECT_MAP.md) · [Suivi de mission](PROJECT_PROGRESS.md).

## Fonctions disponibles

- Catalogue, seuils, mouvements et historique des prix ; versions, stock non négatif et reprise idempotente.
- CRM clients/fournisseurs, notes, tâches, opportunités reliées aux devis.
- Devis, ventes confirmées, retours revendables ou endommagés et documents imprimables. Ventes TTC, coût HT et taxe par ligne ; coûts inconnus explicites.
- Trois imports CSV distincts : catalogue, historique de ventes sans stock, transactions confirmées avec stock. Aperçu et validation atomique.
- Commandes fournisseurs, réceptions partielles, clôture du solde et propositions min/max sous budget tenant compte des engagements.
- Contribution nette, références phares et associations de panier. Il s'agit d'analyse descriptive ; l'effet causal d'un produit d'appel et le bénéfice réel ne sont pas garantis.
- Identité canonique, surveillance de fiches Tunisianet/Mytek/Spacenet, extraction publique bornée, file SQLite, revue humaine et comparaison à conditions égales. Mytek renvoyait HTTP 403 lors de la vérification réelle du 12 octobre ; aucun contournement ni faux prix.
- Alertes de stock, échéances et retards, suivi motivé ; inventaires physiques ; sauvegarde et restauration vers une nouvelle base.
- Flutter : socle stock/prix, espace commercial, consultations, confirmation de vente/devis, réceptions, comptages, notes CRM et prise en charge de décisions. Création détaillée des documents, retours, imports et paramétrage sur le web.

Le ML de demande est un `GradientBoostingRegressor` local comparé à trois références simples sur des périodes chronologiques. Il utilise l'historique et les ventes confirmées nettes des retours ; une semaine inconnue ne devient pas automatiquement zéro. Les anciens modèles de prix ne sont pas reliés au stock réel. Aucun LLM, agent autonome ou token API dans ces fonctions.

## Installation Windows

Python 3.11+, Node compatible Vite (`^20.19.0` ou `>=22.12.0`), npm. Utiliser l'environnement recréé `.venv-local`, jamais le `.venv` fourni ni les anciens joblib non vérifiés.

```powershell
.\scripts\setup.ps1
npm.cmd run build --prefix frontend
.\scripts\run.ps1
```

Le lancement standard utilise `runtime/stock.sqlite3`. Choisir explicitement une autre base avec `-Database 'runtime/ma-boutique.sqlite3'`. Le premier accès crée l'administrateur. ADMIN gère les comptes et sauvegardes ; MANAGER gère les opérations ; VIEWER consulte.

Les évolutions de schéma sont additives (`CREATE TABLE/INDEX IF NOT EXISTS`) ; aucune table ou donnée précédente n'est supprimée. Sauvegarder avant mise à niveau d'une base réelle : [maintenance](docs/MAINTENANCE.md).

Variables : `SMART_STOCK_DB` choisit SQLite ; `SMART_STOCK_COLLECTION=0` arrête le worker de collecte ; `SMART_STOCK_DEMO=1` affiche le bandeau de recette ; `SMART_STOCK_DEV=1` ouvre les outils API de développement. Aucun secret nécessaire pour le fonctionnement local. La collecte n'effectue aucun accès concurrent tant qu'aucune URL n'est activée. Elle cesse à l'arrêt du serveur/PC.

## Développement et contrôles

```powershell
.\scripts\test.ps1
# Ou séparément :
.\.venv-local\Scripts\python.exe -m pytest tests -q
.\.venv-local\Scripts\python.exe -m pip check
npm.cmd run build --prefix frontend
# Vite (proxy vers le backend local) :
npm.cmd run dev --prefix frontend
```

Recettes Chromium : installer les dépendances de `tests`, puis `npm.cmd run test --prefix tests`, `test:design`, `test:delivery` et les scripts métier listés dans `tests/package.json`. `PLAYWRIGHT_MODULE_PATH` permet d'utiliser un runtime Playwright déjà installé. Chaque script crée sa propre SQLite. Captures et résultats dans `docs/evidence`.

Flutter : [installation Android et commandes de validation](docs/MOBILE_INSTALLATION.md). L'APK debug est local ; iOS requiert Mac/Xcode. La production HTTPS, la signature boutique, SMTP et notifications push ne sont pas activés.

Les services ML historiques sous `services/ml_*` sont conservés à part : CSV de démonstration, aucun lien implicite avec les IDs SQLite. [Optimisation et limites de la demande](docs/DEMAND_OPTIMIZATION.md). La performance sur données synthétiques ne certifie pas celle sur des ventes réelles.
