# Consignes des agents IA

Travailler principalement en français. Lire le README, docs/PROJECT_STATE.md et la carte avant la première modification, puis uniquement les fichiers utiles. Vérifier git status et expliquer brièvement les changements importants.

## Architecture

- Frontend React/TypeScript dans frontend/src : API centralisée, composants UI partagés, pages métier.
- Entrée du cœur local : services/api_gateway/app/main.py. Auth, Stock et Alerts partagent libs/common/database.py (SQLite).
- Entraînement et inférence ML sont conservés dans leurs services ; ils utilisent des CSV et artefacts séparés du stock opérationnel.
- Des fichiers vides subsistent : leur nom ne prouve pas une fonction active. Voir PROJECT_STATE.md pour les limites engagées.
- Exclure .venv, .venv-local, node_modules, runtime et artefacts des recherches métier. Cibler services, libs, frontend/src, tests et docs avec rg.

## Règles métier et modification

- Préserver les contrats, les données, la navigation et les frontières Auth/Stock/ML.
- Stock entier, sortie supérieure au disponible refusée. Ajustement = stock cible >= 0 avec motif. Aucun stock direct dans le formulaire produit.
- Mouvements/prix : transaction serveur, version attendue, clé idempotente liée à l'acteur et au payload. Conserver la clé après une erreur réseau si la requête reste identique.
- Prix Decimal en strings, maximum quatre décimales. Ne pas inventer devise, taxes, valorisation ou marge. Plancher uniquement s'il est renseigné.
- Rôles locaux : ADMIN gère aussi les comptes, MANAGER modifie produits/stock/prix, VIEWER consulte. Contrôles côté serveur obligatoires.
- Ne pas utiliser les IDs SQLite seuls pour relier un produit aux CSV ML. Une recommandation nécessite identité, données et provenance concordantes.
- Examiner entraînement et inférence ensemble lorsque des features ou formats d'artefacts changent. Une exécution sur données synthétiques ne valide pas la qualité prédictive.
- Garder les formulaires montés pendant leurs rafraîchissements pour conserver saisies et messages. Ne pas annoncer un succès avant confirmation du serveur.
- Maintenir les états de chargement, vide, refus, erreur, session expirée et succès. Navigation clavier et layouts mobiles à vérifier.

## Sécurité

- Ne jamais supprimer fichiers, modèles, migrations, tables ou données sans confirmation explicite.
- Ne jamais afficher ou remplacer secrets, .env, .env.txt ou identités réelles. Ne pas committer les bases runtime, comptes QA, logs ou environnements.
- Aucun achat, push, publication, déploiement, message externe ou migration de production sans autorisation.
- Ne pas exécuter le .venv reçu. Recréer .venv-local à partir des manifests verrouillés.
- Ne pas désérialiser les anciens joblib non vérifiés. Les sidecars SHA-256 sont des contrôles d'intégrité, pas des signatures ; les dossiers de modèles doivent rester fiables.
- Servir les applications sur 127.0.0.1. Conserver les contrôles Host/Origin et les restrictions loopback des services ML.
- Expliquer toute évolution de schéma et cibler une base distincte pour les tests. Aucun effacement implicite de la base opérationnelle.

## Validation et reprise

- Exécuter scripts/test.ps1 ou pytest + build selon le changement ; ajouter des tests utiles pour les règles métier.
- Recette navigateur : tests/browser.mjs et tests/browser-design.mjs ; vérifier ordinateur/mobile, actions, clavier, overflow et erreurs JavaScript.
- Utiliser uniquement les bases temporaires et données de recette pour les tests.
- Livrer fichiers, contrôles exécutés, captures pertinentes et limites. Ne pas affirmer que tout le projet fonctionne sans preuves.
- Mettre à jour docs/PROJECT_STATE.md et la carte quand architecture, périmètre ou état vérifié changent. Ne pas confondre local, testé et déployé.
