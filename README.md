# Smart Stock Management & Pricing

Application locale de gestion du stock en français. Le frontend React/TypeScript utilise les API FastAPI et une vraie base SQLite. Les données saisies persistent après rechargement et redémarrage. Aucun produit ou compte CSV de démonstration n'est importé automatiquement.

## Fonctionnalités utilisables localement

- Premier administrateur, connexion, déconnexion et comptes ADMIN / MANAGER / VIEWER avec contrôles serveur.
- Produits : création, recherche par nom/SKU/catégorie, filtres de stock, tri, fiche et modification des informations.
- Entrées, sorties et ajustements avec motif, récapitulatif, transaction, version attendue et idempotence.
- Historique des mouvements, alertes sous le minimum/au-dessus du maximum et tableau de bord calculé côté serveur.
- Prix actuel, application explicite d'un nouveau prix, plancher facultatif et historique. Quatre décimales conservées, sans devise/taxe présumée.
- Frontend adapté aux mobiles et catalogue des composants réservé au développement.

Les fonctions ML existantes sont conservées et testées séparément sur des données synthétiques. **Les recommandations sur le stock opérationnel restent indisponibles tant qu'un historique correspondant et des modèles validés ne sont pas explicitement liés.** Le projet complet n'est donc pas déclaré finalisé ni prêt à être exposé en production.

## Installation Windows / PowerShell

Prérequis : Python 3.11 ou supérieur (validation effectuée avec 3.11.6), Node compatible avec Vite (`^20.19.0` ou `>=22.12.0`) et npm. La validation de cette session a utilisé Node 25.2.1. Depuis la racine du dépôt :

```powershell
.\scripts\setup.ps1
# Si nécessaire, préciser votre interpréteur local :
# .\scripts\setup.ps1 -Python 'C:\chemin\vers\python.exe'
.\scripts\run.ps1
```

Le script d'installation crée `.venv-local`, installe `requirements-lock.txt`, utilise `npm ci` avec `frontend/package-lock.json`, puis compile le frontend. Il n'exécute pas les binaires du `.venv` reçu et ne supprime aucun fichier existant. Si votre politique PowerShell empêche l'exécution de scripts, utiliser les commandes manuelles ci-dessous sans modifier votre politique globale.

Après lancement, ouvrir [l'application locale](http://127.0.0.1:8000). Créer votre premier administrateur avec un mot de passe de 12 à 256 caractères contenant une majuscule et un chiffre. Aucun email ni lien d'activation n'est envoyé.

```powershell
python -m venv .venv-local
& .\.venv-local\Scripts\python.exe -m pip install -r requirements-lock.txt
Set-Location frontend
npm.cmd ci --cache .npm-cache
npm.cmd run build
Set-Location ..
& .\.venv-local\Scripts\python.exe -m uvicorn services.api_gateway.app.main:app --host 127.0.0.1 --port 8000
```

Le serveur sert le frontend compilé et les API sur la même origine. Un seul service est nécessaire pour le cœur stock. Arrêt par Ctrl+C. Base par défaut : `runtime/stock.sqlite3`, jamais les CSV de `data/`. Sauvegarder cette base avant toute évolution future de schéma.

## Configuration

`.env.example` contient uniquement des noms et exemples non secrets. Le cœur lit `SMART_STOCK_DB` et `SMART_STOCK_DEV` dans l'environnement du processus. Il ne charge pas automatiquement `.env`. Ne pas copier `.env.txt` sans revue ; ce fichier d'origine est conservé et n'est pas utilisé pour l'authentification locale.

```powershell
# Autre base locale, sans toucher à la base par défaut :
.\scripts\run.ps1 -Database 'runtime/essai.sqlite3' -Port 8000
```

La nouvelle base crée uniquement les tables `users`, `sessions`, `login_attempts`, `products`, `movements`, `price_history` et `idempotency` si absentes. Il ne s'agit pas d'une migration distante. Les nouveaux fichiers runtime, environnements et artefacts sont ignorés. Le `.venv`, `.env.txt` et les anciens modèles déjà suivis ne sont pas retirés de Git par le `.gitignore`.

## Développement et design system

Dans un terminal, lancer le cœur :

```powershell
.\scripts\run.ps1 -Dev
```

Dans un autre terminal :

```powershell
Set-Location frontend
npm.cmd run dev
```

Ouvrir [le frontend de développement](http://127.0.0.1:5173), puis `/design` après connexion. La page réutilise Button, Field, Badge, Notice, Empty, Loading et Modal des écrans réels. Le proxy `/api` conserve Host pour le contrôle Origin. La version compilée ne propose pas ce catalogue ; `/design` est refusé par le serveur lorsque `SMART_STOCK_DEV=0`.

## Vérifications

```powershell
.\scripts\test.ps1
# Équivalent serveur :
& .\.venv-local\Scripts\python.exe -m pytest tests -q
```

Pour réinstaller et exécuter la recette navigateur :

```powershell
Set-Location tests
npm.cmd ci --cache .npm-cache
npx.cmd playwright install chromium
npm.cmd test
npm.cmd run test:design
Set-Location ..
```

Les scripts navigateur créent et arrêtent leurs propres serveurs, sans supprimer les données opérationnelles. `browser.mjs` utilise le port 8010 et une SQLite neuve sous `runtime/browser-qa-*`. Le script design requiert les ports 8000 et 5173 libres et utilise une autre base QA. Les captures et résultats sont dans `docs/evidence`. Les comptes et produits utilisés sont identifiés comme recette.

Résultats vérifiés : **37 tests Python réussis**, compilation TypeScript/Vite réussie, audit npm du frontend sans vulnérabilité signalée, deux recettes navigateur réussies et zéro erreur JavaScript relevée. Voir [l'état détaillé](docs/PROJECT_STATE.md) et [les preuves](docs/evidence/browser-results.json). Un avertissement Starlette signale la future évolution de son adaptateur httpx de test ; aucun test n'échoue.

## Services ML

Les services ML sont facultatifs pour le stock, réservés aux clients loopback et aux origines locales pour l'entraînement. Les modèles suivis d'origine ne sont pas chargés : seuls les artefacts issus d'un entraînement local explicite avec empreinte et métadonnées concordantes sont acceptés. Une empreinte SHA-256 détecte les altérations ; ce n'est pas une signature de confiance.

```powershell
$env:DATA_DIR = Join-Path $PWD.Path 'data'
$env:MODELS_DIR = Join-Path $PWD.Path 'artifacts/models'
$env:REPORTS_DIR = Join-Path $PWD.Path 'artifacts/reports'
# Premier terminal, réservé aux données fictives du dépôt :
& .\.venv-local\Scripts\python.exe -m uvicorn services.ml_training_service.app.main:app --host 127.0.0.1 --port 8001
# Autre terminal avec les mêmes variables :
& .\.venv-local\Scripts\python.exe -m uvicorn services.ml_inference_service.app.main:app --host 127.0.0.1 --port 8002
```

Les routes et entraînements correspondants sont dans [la carte du projet](docs/PROJECT_MAP.md). Un POST d'entraînement écrit des modèles et rapports ; il ne doit viser que des dossiers que vous contrôlez. Aucun entraînement n'est exposé dans le frontend métier. La recette automatisée vérifie cinq entraînements et six inférences sur des CSV synthétiques isolés, pas la qualité prédictive sur des données réelles.

## Documentation et limites

- [Instructions des agents](AGENTS.md)
- [État, périmètre et prochaine action](docs/PROJECT_STATE.md)
- [Architecture et flux](docs/PROJECT_MAP.md)
- [Audit IA initial et actualisation](docs/AI_READINESS.md)
- [Inventaire de recette](docs/QA_INVENTORY.md)
- [Revue backend et corrections](docs/REVIEW_BACKEND.md)

Non livrés : lien d'un historique réel aux recommandations ML, qualité prédictive validée, activation/récupération de mot de passe par email, désactivation/révocation globale de comptes, frontière multi-organisation, import des ventes ou datasets par une interface, déploiement et certification de production. Aucun achat, publication, migration de production ou push n'a été effectué. Les données saisies sont locales ; aucune synchronisation cloud n'est activée.
