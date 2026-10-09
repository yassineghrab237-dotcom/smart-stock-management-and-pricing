# État de reprise — 9 octobre 2026

## Résultat et périmètre retenu

**UTILISABLE LOCALEMENT et TESTÉ** : application React/TypeScript en français reliée à FastAPI et SQLite. Connexion, droits, catalogue, mouvements, historique, alertes et prix appliqués persistent réellement. Aucun déploiement ni push. Les CSV et comptes fictifs du dépôt ne sont pas importés dans la base opérationnelle.

Le dépôt initial était majoritairement un squelette. Les modules métier ont été implémentés localement ; il ne s'agissait pas de finaliser une application existante déjà raccordée. Le projet complet reste **NON TERMINÉ** pour les recommandations ML sur historique métier réel et les autres intentions listées ci-dessous.

## Hypothèses prudentes

- Utilisateur provisoire : gestionnaire non technique ; interface française.
- Quantités entières, sorties supérieures au stock refusées. Ajustement = quantité physique cible, motif obligatoire et trace avant/après.
- Produit neuf à stock zéro ; aucune suppression de produit ni d'historique exposée.
- Montants à quatre décimales, sans devise, taxes, méthode de valorisation ou conversion d'unité inventée.
- Comptes locaux ADMIN, MANAGER, VIEWER ; aucune organisation ou frontière multi-tenant existante n'a été trouvée.
- Premier admin créé via formulaire local ; mots de passe 12 à 256 caractères, majuscule et chiffre. Aucun email d'activation ou reset envoyé.
- Frontend ajouté en React/TypeScript/Vite, backend FastAPI conservé. SQLite est un nouveau stockage local adapté au périmètre mono-instance ; aucune migration distante.

## Matrice de livraison

| Fonction/parcours | Preuve | État | Correction et critère vérifié |
|---|---|---|---|
| Connexion / droits | routes Auth + tests HTTP + recette design | TESTÉ | sessions hachées, cookies, expiry, limites login ; refus 401/403 |
| Premier admin | tests setup concurrent + navigateur | TESTÉ | un seul premier compte, rôle serveur |
| Catalogue | API produits, SQLite, navigateur | TESTÉ | création, rechargement et redémarrage conservent produit ; SKU unique |
| Recherche / filtres / détail | recette browser.mjs | TESTÉ | nom/SKU/catégorie, filtre et retour liste gardant contexte |
| Mouvements / historique | tests SQL via HTTP et navigateur | TESTÉ | 100 - 15 + 20 = 105 ; avant/après, auteur, motif |
| Double soumission / concurrence | tests + perte de réponse après commit | TESTÉ | idempotence ; conflit version 409 ; aucune écriture perdue ou doublonnée |
| Invalides / ajustements | suite serveur et UI | TESTÉ | sortie excessive, bool/float, motif vide, overflow refusés sans écriture partielle |
| Alertes | seuils produits et tests | TESTÉ | stock inférieur au min ou supérieur au max ; résolution dérivée d'une opération |
| Prix appliqué / historique | Decimal + tests + UI | TESTÉ | quatre décimales, plancher renseigné, droits, version, action explicite |
| Formulaires prix | régression navigateur | TESTÉ | succès durable ; conflit garde la saisie puis reconfirmation |
| Design system / responsive | captures + design-results.json | TESTÉ | composants des vrais écrans, 390/768/1440 sans overflow, opérations réelles, Tab/Escape |
| ML exécution | test_ml.py isolé | TESTÉ SUR SYNTHÉTIQUE | 5 entraînements + 6 inférences, erreurs/provenance, anciens modèles refusés |
| ML qualité et stock opérationnel | aucune source liée dans la base métier | MANQUANT | interface honnête unavailable ; pas de recommandation fabriquée |
| Import catalogue / ventes | tests/test_imports.py + browser-imports.mjs | TESTÉ | aperçu, rapprochement SKU exact, atomicité, doublons, conflits, droits ; ventes sans mouvement de stock |
| Pipeline ml_data_service | service original encore squelette | MANQUANT | pas d'export vers corpus ML ni de liaison des modèles aux ventes importées |
| Activation/reset email | non raccordé | MANQUANT | aucun envoi activé, aucune fausse confirmation |
| Production / multi-organisation | non déployé | NON VÉRIFIÉ | aucun certificat production, cloud, backup/restore ou isolation multi-tenant |

## Jalons et preuves

- **J1 réalisé** : dépôt et branche vérifiés, travail local conservé, .venv-local neuf, requirements-lock.txt et verrous npm ; .env.example non secret, .gitignore adapté. Le .venv versionné est conservé.
- **J2 réalisé** : parcours HTTP persistant, transactions SQLite, versions et clés d'idempotence. Données d'essai exclusivement temporaires.
- **J3 réalisé** : frontend connecté et design system partagé, layout table/cartes, erreurs et vides, focus et navigation mobile.
- **J4 partiel** : alertes et tarification manuelle testées ; entraînement/inférence ML fonctionnent sur des CSV synthétiques isolés. L'exploitation sur historique réel reste non livrée.
- **J5 réalisé pour le périmètre local** : revue backend distincte, corrections Host/IDs, recette navigateur, captures, documentation et revue du diff. Ce n'est pas une recette avec de vrais utilisateurs.

Contrôles exécutés :

- pytest tests -q : **58 passed**, dont 21 cas CSV ; un avertissement de dépréciation du client httpx par Starlette, sans échec.
- pip check : aucune incompatibilité signalée.
- npm run build : TypeScript strict et Vite réussis.
- npm audit frontend : **0 vulnérabilité signalée**, dépendances dev incluses. Vite mis à jour de 7.1.9 à 7.3.7 après alerte du registre ; aucun changement majeur.
- browser.mjs : parcours réel, stock 105, persistance, mobile/tablette/desktop, prix, conflit, retry, alertes et réseau. Zéro pageerror JavaScript.
- browser-design.mjs : proxy local, design interactif, collaborateur VIEWER, actions et refus serveur ; zéro pageerror JavaScript.
- browser-imports.mjs : catalogue et ventes, aperçu, doublon bloquant, stock/prix conservés, retry après réponse perdue, historique persistant et VIEWER ; 390/768/1440 sans overflow, Escape/focus ; zéro pageerror JavaScript.
- Revue séparée docs/REVIEW_BACKEND.md : les deux constats ont été corrigés et couverts par régressions Host externe/IDs démesurés.

Résultats conservés dans docs/evidence : pytest-results.xml, browser-results.json, design-results.json, produits et mouvements 390/768/1440, design et lecture seule desktop. Captures contenant uniquement des comptes/produits de recette, jamais une identité réelle.

## Défauts corrigés pendant la recette

- Labels de formulaires : descriptions séparées du nom accessible via aria-describedby.
- Prix : formulaire conservé pendant refresh/refetch pour ne pas perdre succès ou saisie lors d'un conflit.
- Mobile : navigation fermée non tabulable, trap focus quand ouverte, Escape et retour au déclencheur.
- Changement ADMIN vers VIEWER : remise à zéro de la navigation pour éviter un écran inaccessible vide.
- Composants produits/stock/prix séparés dans frontend/src/features ; le catalogue n'embarque plus tous les formulaires dans un fichier unique.
- Indicateur quantités : somme brute explicitée, sans conversion d'unités supposée.
- Sécurité : Host limité, IDs SQLite bornés, politique du mot de passe réellement contrôlée, Origin vérifié aussi pour les entraînements ML.

## Limites et prochaine tâche

Le lien entre stock opérationnel, historique de ventes et modèles ML reste à construire et vérifier. L'adaptateur exige une provenance et une identité explicitement liées ; aucun champ public de produit ne permet actuellement d'activer ce lien. Les modèles synthétiques ne sont pas qualifiés pour fixer des prix réels. Ce travail ne doit pas être annoncé terminé.

Import d'historique livré : format documenté dans CSV_IMPORTS.md, aperçu complet, correspondance SKU exacte, transaction et confirmation explicite. Les données restent en SQLite, séparées des CSV démo. Au démarrage, deux tables additives csv_imports et sales_history sont créées si absentes ; aucune donnée existante n'est remplacée. Les ventes importées ne décrémentent pas le stock actuel.

Prochaine tâche exécutable : exporter les ventes et le catalogue vers un corpus ML identifié et versionné, gérer leur provenance déclarée et les données nécessaires manquantes, puis entraîner/évaluer hors entraînement sur un corpus métier autorisé avant de lier les modèles et proposer des recommandations. Aucun corpus réel n'a été importé pour cette recette.

Autres intentions non livrées : activation et récupération email, désactivation de comptes, révocation globale de sessions, workflow de décisions sur recommandations, collecte concurrentielle, export/pipeline des datasets ML, services de données, déploiement et recovery. Aucun emplacement, réservation, transfert, comptabilité, paiement, chatbot ou application native ajouté.

Le fichier d'origine data/config.json décrit aussi des intentions d'alertes liées au délai fournisseur, un ratio de surstock et une escalade après 24 h. Ces règles avancées ne sont pas raccordées dans le premier périmètre : les alertes livrées utilisent les seuils min/max renseignés sur le produit et l'interface en explique la règle. Aucun indicateur de délai ou d'escalade n'est simulé.

## Relancer

Depuis la racine : scripts/setup.ps1 puis scripts/run.ps1. Le cœur démarre à 127.0.0.1:8000, avec la base runtime/stock.sqlite3. Les scripts de recette arrêtent leurs propres serveurs ; aucune exécution en arrière-plan n'est promise. Pour poursuivre les tests : scripts/test.ps1, puis les deux scripts navigateur décrits dans le README.

## Commits locaux

- 300099e : cœur persistant, sécurisation, services ML et tests Python.
- 1c79d63 : frontend français, composants séparés et recettes navigateur.
- Documentation et preuves : commit suivant, consultable avec git log -3 --oneline.

Aucune identité Git n'était configurée. Les commits utilisent uniquement l'auteur technique Codex local agent <codex@localhost>, via options limitées aux commandes ; aucune configuration Git globale ni identité humaine n'a été remplacée. Aucun push.
