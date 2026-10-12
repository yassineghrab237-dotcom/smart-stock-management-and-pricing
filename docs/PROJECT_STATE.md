# État de livraison — 12 octobre 2026

Le périmètre commercial local est implémenté pour recette. Le dépôt distant n'a pas été modifié. Aucune donnée opérationnelle n'a servi aux tests, aucun compte réel ou secret n'a été remplacé, aucun achat ou déploiement effectué.

## Fonctions et limites

| Fonction | État actuel |
|---|---|
| Auth, rôles, révocation | Testés, contrôlés côté serveur, cookies web et Bearer mobile distincts |
| Catalogue, stock, prix | Transactions, versions, historique et idempotence testés |
| CRM | Contacts, fournisseurs, tâches, notes, opportunités, devis liés ; aucun envoi externe |
| Commerce | Devis/vente/confirmation/conversion, retours, documents imprimables ; pas de facture fiscale certifiée |
| CSV | Catalogue, historique sans mouvement, transactions avec stock ; dates métier et doublons intersources |
| Achats | Commandes et réceptions partielles, clôture du solde, contraintes fournisseur |
| Réassort | Min/max, stock et engagements, budget HT, minimum/colis et brouillon ; pas d'optimiseur de bénéfice |
| Analyse commerciale | Contribution après retours, coûts manquants explicites, références phares et paniers associés |
| Demande ML | Validation chronologique, 3 références simples, réglage borné dès 24 semaines, données opérationnelles incluses ; qualité réelle non certifiée |
| Identité et matching | Canonique versionnée, GTIN contrôlé, référence/variante/garantie, décision humaine et historique |
| Collecte | Worker local et file SQLite durable, URLs activées explicitement, cadence et accès bornés, erreurs visibles |
| Sources réelles | Robots des 3 enseignes accessibles ; prix extrait sur une fiche Tunisianet et Spacenet ; Mytek HTTP 403 observé |
| Comparaison | Même identité/variante, devise, taxes, livraison et stock annoncé, fraîcheur 24 h ; aucune écriture automatique du prix interne |
| Décisions | Stock, échéances CRM, achats en retard, matching et prix périmés ; suivi versionné avec motif |
| Inventaires | Comptage sans mouvement puis ajustements atomiques, conflits/recompte, historique |
| Maintenance | Sauvegarde SQLite cohérente, empreinte et intégrité, restauration uniquement vers nouveau fichier ; récupération admin locale auditée |
| Web | React strict, responsive, clavier, reprise réseau et erreurs ; recettes navigateur métier |
| Flutter | Socle + consultations commerciales, confirmation des documents existants, réceptions, comptages, CRM et décisions ; détail de validation ci-dessous |
| Production / iOS | Non déployée ; compilation/signature iOS indisponibles sous Windows |

Les produits d'appel ne peuvent être prouvés par une corrélation de panier. Les frais externes, la valorisation comptable du stock et la rotation en valeur demandent une politique de coût et des données exhaustives. Les rôles ne constituent pas une séparation multi-organisation. L'étude de toutes les entreprises du marché n'est pas couverte : trois enseignes et les fiches configurées sont suivies.

## Vérifications

- Suite Python globale : **155 tests réussis**, puis **22 tests collecte/décisions/maintenance** après les derniers contrôles de fichier SQLite malformé, de lecture réseau et de disponibilité vérifiée. Total inventorié : 157 tests, dont un contrôle supplémentaire de disponibilité absente puis vérifiée manuellement.
- `pip check` sans incompatibilité ; TypeScript/Vite compilés.
- Chromium : cœur stock/prix, design/rôles, imports, livraison/ML ; CRM, commerce, achats, analyses, réassort, transactions, B2B/impression, maintenance, inventaires, collecte et décisions. Scénarios métier incluent réponses perdues, doublons, erreurs/conflits, persistance et largeurs 1440/768/390. Captures sous `docs/evidence`.
- Recettes de collecte sur fixtures : succès, robots, erreur, identité modifiée, contradiction MPN, pause, reprise et contrôle réseau public. Les sondes réelles sont séparées dans `collection-live-probe*.json`.
- Flutter : analyse sans erreur et **11 tests réussis**. Les deux parcours Android sur émulateur avec serveur réel sont réussis : socle stock/prix/reprise et parcours commercial vente/réception/inventaire/CRM/rentabilité. Captures natives inspectées. APK normal reconstruit après les tests (preuve dans native-build.json).
- Un avertissement de dépréciation Starlette/httpx concerne l'adaptateur de tests ; aucun changement de dépendance gratuit.

## Architecture et migrations

FastAPI partage `libs/common/database.py`. Les mutations métier utilisent `BEGIN IMMEDIATE`, versions et clés idempotentes liées à l'acteur et au contenu. Les montants sont des Decimal textuels à quatre décimales. Les prix catalogue historiques n'acquièrent pas arbitrairement une devise ou base fiscale.

Les tables additives de cette extension sont : `crm_contacts`, `crm_events`, `crm_tasks`, `crm_opportunities`, `commercial_documents`, `commercial_lines`, `commercial_returns`, `commercial_sale_dates`, `purchase_orders_local`, `purchase_lines_local`, `purchase_receipts_local`, `replenishment_policies`, `replenishment_events`, `inventory_sessions`, `inventory_lines`, `inventory_events`, `market_observations`, `product_identities`, `collection_watches`, `collection_jobs`, `collection_hosts`, `collection_events`, `decision_events`, `local_recovery_events`. Elles s'ajoutent au socle, sans suppression ni remplacement.

La collecte se lance avec le serveur local, uniquement pour les URL activées. File persistante, verrouillage de prise en charge, récupération des tâches interrompues après 20 minutes, prochaine échéance et pause conservées. Pas de fonctionnement PC éteint. `SMART_STOCK_COLLECTION=0` désactive le worker sans effacer les demandes.

Le calcul ML reste un job local en mémoire avec progression/résultat stockés. `BackgroundTasks` n'est pas une file durable ML ; une analyse inactive est signalée interrompue. Aucun joblib historique n'est chargé.

## Recette

`run-recipe.ps1` sélectionne une base explicitement fictive ; `-New` crée une autre base. Compte généré dans son fichier `ACCES_RECETTE.txt`, non suivi dans Git. Le démarrage standard `run.ps1` conserve le choix explicite de base. Voir [les scénarios utilisateur](RECETTE_UTILISATEUR.md).

Avancement de recette locale estimé : **95 % (19 lots sur 20 entièrement validés)** ; le lot restant concerne l’accès réel à Mytek (HTTP 403), pas l’existence du connecteur. Le détail de la grille est dans PROJECT_PROGRESS.md. Production et iOS ne sont pas inclus dans ce pourcentage.
