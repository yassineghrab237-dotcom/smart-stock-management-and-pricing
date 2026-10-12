# État de livraison — 12 octobre 2026

## Optimisation de la demande

Le moteur v2 ajoute des indicateurs sur les quatre semaines récentes, compare trois configurations sur deux périodes temporelles antérieures au contrôle final et conserve les réglages initiaux si le gain de validation ne dépasse pas 5 %. Le réglage automatique commence à 24 semaines ; de 16 à 23, les paramètres restent fixes. Le contrôle final impose de battre trois méthodes simples. L’empreinte inclut la version de méthode : les anciens jobs sont conservés et signalés périmés.

Suite serveur actuelle : **78 tests réussis**. TypeScript/Vite compilés et recette Chromium livraison réussie. Le benchmark compare huit séries synthétiques : deux erreurs améliorées, cinq identiques à quatre décimales, une dégradée ; deux prévisions supplémentaires masquées parce qu’une méthode simple est parfaite. Le calcul est plus coûteux. Ces cas ont servi au développement et ne prouvent pas un gain sur des ventes réelles. Voir [les mesures détaillées](DEMAND_OPTIMIZATION.md).

Les validations natives de parcours complet ci-dessous datent du 11 octobre ; cette évolution conserve le contrat API et ne change que le texte natif expliquant les résultats périmés.

Le 12 octobre : `flutter analyze` sans erreur, 8 tests Flutter réussis et APK debug normal recompilé ; empreinte actualisée dans evidence/native-build.json. Les captures web 390/768/1440 montrent la nouvelle méthode et la référence comparée ; la vue 390 a aussi été inspectée visuellement.

## Résultat local

Le périmètre réalisable sur ce PC comprend le cœur FastAPI/SQLite, le web React/TypeScript français, les imports CSV, la gestion des accès, une analyse de demande sur ventes importées et un client natif Flutter Android/iOS. Aucun achat, push, publication, migration distante ou déploiement. Les CSV de démonstration, le `.venv`, `.env.txt` et les 40 joblib historiques restent conservés.

| Fonction | État et preuve |
|---|---|
| Connexion, rôles et sessions | TESTÉ : cookies web et Bearer mobile indépendants, jetons hachés, expiration, limite de connexion partagée |
| Catalogue, mouvements et prix | TESTÉ : SQLite persistante, versions, transactions, idempotence, historique et permissions ; aucun stock négatif |
| Désactivation et révocation globale | TESTÉ : ADMIN uniquement, confirmation, motif, sessions fermées, réactivation sans restaurer les anciens jetons ; aucun compte supprimé |
| CSV catalogue et ventes | TESTÉ : aperçu, rapprochement SKU explicite, atomicité, doublons, historique ; les ventes importées ne modifient pas le stock |
| Demande depuis les ventes SQLite | TESTÉ sur historique QA explicitement synthétique : job suivi jusqu’au résultat, validation temporelle et comparaison naïve, résultat périmé masqué |
| Anciennes recommandations de prix ML | NON RELIÉES au stock réel ; anciens services testés séparément, aucun modèle historique chargé |
| Web français et aide | COMPILÉ et TESTÉ dans Chromium, mobile/tablette/desktop, navigation clavier, erreurs et réseau ; captures docs/evidence |
| App Flutter native | IMPLÉMENTÉE : connexion, catalogue, stock/prix confirmés, alertes, historique, analyses et reprise sécurisée ; analyse statique et huit tests réussis |
| Android | COMPILÉ et TESTÉ : parcours natif complet sur émulateur, stockage sécurisé réel, reprise sans doublon et cohérence web ; QA_INVENTORY.md |
| iOS | SOURCES et configuration Keychain livrées ; compilation/signature/recette NON EXÉCUTÉES sur ce Windows |
| Production et boutiques | NON DÉPLOYÉ ; service local loopback, pas de clé de production, SMTP, push ou cloud |

## Architecture et données

Le web et le mobile utilisent les mêmes routes métier et la même base du service. La session mobile dure douze heures et ne remplace pas les cookies. Le mot de passe n’est jamais sauvegardé par Flutter. Les mouvements/prix sauvegardent une requête et sa clé dans le stockage sécurisé avant envoi, et exigent une reprise manuelle après erreur. Une ancienne version provoque un refus serveur ; consulter l’historique et actualiser avant de préparer une nouvelle opération.

Les ajouts de schéma sont exclusivement `CREATE TABLE IF NOT EXISTS` : `mobile_sessions`, `analysis_jobs`, `user_access`. Aucune table précédente vidée ou remplacée. Les comptes précédents restent actifs par défaut. Désactiver révoque les sessions et conserve les comptes et historiques.

L’analyse utilise des semaines terminées, consécutives jusqu’à la semaine dernière, au moins seize par produit. Elle ne fabrique pas de ventes nulles quand une semaine est inconnue. Quatre semaines sont réservées à l’évaluation chronologique ; la prévision est cachée si le modèle ne bat pas la dernière semaine répétée. Résultats JSON et progression sont enregistrés ; date et empreinte signalent les résultats anciens. Aucun joblib chargé, stock/prix modifié ou appel LLM : zéro token API consommé par cette fonction.

`BackgroundTasks` n’est pas une file durable : après dix minutes sans progression, la prochaine consultation signale l’interruption et permet un nouveau lancement. Une seule analyse active par base et déduplication par empreinte évitent de répéter un calcul sur une réponse perdue. La provenance est déclarée comme historique importé par l’utilisateur, jamais certifiée automatiquement.

## Vérifications exécutées

- Suite Python complète : **78 passed**, un avertissement Starlette/httpx sans échec ; XML conservé.
- `pip check` : aucune incompatibilité.
- TypeScript strict et Vite : compilation réussie.
- Recettes Chromium cœur, design, CSV et livraison : résultats JSON et captures dans `docs/evidence`, zéro erreur JavaScript relevée.
- Livraison web : premier accueil, guide 390/768/1440, analyse complète sans écriture de stock, invalidation des prévisions, comptes activés/désactivés et révocation confirmée.
- Flutter : `flutter analyze` sans erreur, **8 tests réussis** dont transport HTTPS, formulaires 320/390/768, même clé après réponse perdue, changement d’onglet en cours de chargement et fiche bloquée pendant son rafraîchissement.
- Aucun test ne vise la base opérationnelle ou une identité réelle. Les captures utilisent exclusivement des comptes et produits QA.

## Corrections issues de la recette

La fiche native retenait brièvement l’ancien résultat pendant son rechargement, et le changement d’onglet pouvait réinterpréter la structure du précédent résultat. Les écrans attendent maintenant la fin du nouveau chargement ; les actions de prix ne peuvent plus partir avec cette ancienne version. Deux tests couvrent ces régressions. Les protections serveur avaient refusé l’écriture périmée.

Le port 5173 étant utilisé par un autre projet sur ce PC, la recette design a été déplacée sur 5281. Aucun processus de l’autre projet n’a été arrêté.

## Usage et reprise

Depuis la racine : `scripts/setup.ps1` puis `scripts/run.ps1`. Application à `http://127.0.0.1:8000`, SQLite `runtime/stock.sqlite3`, arrêt Ctrl+C. [Guide quotidien](COMMENCER_EN_5_MINUTES.md), [installation native](MOBILE_INSTALLATION.md), [carte du code](PROJECT_MAP.md).

La variante Android locale exige un tunnel USB `adb reverse` vers le PC ; aucun accès Wi-Fi/Internet n’est activé. Après une recette `flutter drive`, reconstruire l’APK normal avant installation. Les serveurs QA et l’émulateur dédié sont arrêtés après validation ; aucun fonctionnement permanent en arrière-plan promis.

## Limites restantes

Il faut un Mac/Xcode pour compiler et tester iOS, une identité et signature de production pour les boutiques, et un déploiement HTTPS explicitement autorisé pour l’accès distant. La qualité prédictive sur un corpus métier réel reste à mesurer. Les recommandations de prix anciennes, délais fournisseur/escalades avancées, frontière multi-organisation, email de récupération, push, sauvegarde/restauration validée et file de travaux durable ne sont pas livrés. Aucun compte boutique, clé ou abonnement acheté ou remplacé.

Les commits sont locaux, auteur technique `Codex local agent <codex@localhost>` limité à la commande ; aucune configuration Git globale modifiée. Voir `git log --oneline` pour les jalons. Le dépôt distant reste inchangé.
