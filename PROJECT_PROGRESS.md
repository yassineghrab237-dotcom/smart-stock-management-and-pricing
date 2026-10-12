# Finalisation autonome de Precios

Mission préparée pour remise en recette le 12 octobre 2026. Objectif : livrer le périmètre réalisable localement, intégré et prêt à la recette. Ne pas arrêter après un seul module. Conserver données, authentification, versions et idempotence. Aucun push, dépenses, messages externes ou déploiement sans autorisation. Base de recette distincte obligatoire.

## Décisions confirmées
- Marché tunisien, références Tunisianet, Mytek et Spacenet.
- Le dépôt fourni est complet. Les revendications du rapport non présentes dans le code restent à réaliser.
- CRM + ventes réelles/paniers + rentabilité + achats/réassort + veille et assortiment constituent le périmètre.
- Autorisation de développement autonome donnée dans la mission jointe du 12 octobre.

## Réponses utilisateur confirmées
1C confirmé : parcours mixte particuliers/entreprises.
2A confirmé : saisie et import CSV des ventes.
3A confirmé : TND, ventes TTC, coûts HT, taxe renseignée par ligne.
Pas de conversion des montants historiques sans métadonnées. Contacts et tâches indépendants de ces réponses.

## Inventaire et backlog dans l'ordre d'exécution
| Fonction | État | Suite et critère de recette |
|---|---|---|
| Authentification, rôles, révocation | TERMINÉE | Régression globale finale |
| Catalogue, mouvements, prix/historique | TERMINÉE | Préserver transactions, version et idempotence |
| Imports catalogue/ventes historiques | TERMINÉE | Conserver distinction import historique vs ventes opérationnelles |
| Demande ML locale | TERMINÉE | Testée sur données synthétiques, pas de performance réelle certifiée |
| Veille manuelle | TERMINÉE | 20 tests dédiés, reprise réseau et UI vérifiées |
| CRM contacts et fournisseurs | TERMINÉE | Créer/éditer/rechercher, historique, droits |
| Interactions et tâches CRM | TERMINÉE | Notes tracées, échéances, clôture |
| Ventes et paniers | TERMINÉE | Saisie, import CSV opérationnel et historique distincts, stock atomique, reprise vérifiée |
| Retours | TERMINÉE | Reliés aux lignes, limites cumulées, revendable ou non |
| Devis et opportunités | TERMINÉE | Devis vers commande, historique et statuts |
| Commandes fournisseurs | TERMINÉE | Coûts, délais, contraintes et commandes ouvertes |
| Réceptions partielles | TERMINÉE | Quantités restantes, stock, doublons et concurrence |
| Réapprovisionnement | TERMINÉE | Règles min/max sur stock et engagements, colis/minimum/budget, brouillon lié aux achats |
| Marges et assortiment | PARTIELLEMENT IMPLÉMENTÉE | Contribution nette, classement et associations vérifiés ; rotation en valeur requiert valorisation fiable |
| Identité produit et matching | TERMINÉE | Canonique versionnée, GTIN contrôlé, validation tracée, contradictions refusées |
| Collecte concurrentielle | TERMINÉE | Extraction bornée et validation ; Mytek HTTP 403 observé, sans contournement |
| Planification durable de collecte | TERMINÉE | File SQLite, échéances, pause/reprise, service local tant que serveur actif |
| Alertes décisionnelles | TERMINÉE | Conditions courantes, suivi versionné, motifs et historique |
| Inventaires physiques | TERMINÉE | Campagne de comptage et écarts ; ajustements existants |
| Sauvegarde/restauration | TERMINÉE | Test sur copie isolée, jamais écraser implicitement |
| Récupération d'accès locale | TERMINÉE | Mécanisme admin maîtrisé sans SMTP inventé |
| Web responsive | TERMINÉE | À revalider pour chaque module nouveau |
| Mobile natif | TERMINÉE POUR RECETTE ANDROID | Socle et espace commercial vérifiés sur émulateur ; formulaires détaillés sur le web |
| Documentation et scénarios recette | TERMINÉE | Guide complet, base fictive, compte généré et serveur démarré |
| Déploiement distant / signature iOS | BLOQUÉE | Pas de cible/autorisation distante, iOS requiert Mac/Xcode |

## Audit technique
FastAPI gateway partage SQLite et règles serveur ; React/TypeScript/Vite même origine ; Flutter natif utilise Bearer. Services ML historiques séparés sur CSV fictifs, ne pas charger les joblib d'origine. Les nombreuses classes/fichiers vides ne sont pas des fonctions livrées. Les tests isolent leur SQLite. Pas de multi-organisation ni hébergement distant actif.

## Validations précédentes conservées
98 tests Python, pip check, build TS/Vite, Chromium marché et régression stock/design réussis lors du lot veille manuelle. Native : dernières validations datent du lot précédent, à refaire pour toute évolution native. CRM : validations dédiées ci-dessous ; régression globale à exécuter après intégration commerciale.

## Travaux en cours et reprise
**Point de reprise actuel :** périmètre local livré et serveur de recette démarré sur 127.0.0.1:8000, base indiquée dans runtime/latest-recipe.json. Prochaine action : exécuter les scénarios utilisateur et traiter leurs retours. Les paragraphes suivants sont le journal chronologique ; leurs anciennes prochaines tâches sont dépassées. Mytek HTTP 403, iOS et production distante restent les limites externes documentées.

## Lot commercial vérifié
API et web devis/brouillons/confirmation de vente/conversion/annulation/retours intégrés. TND TTC, taxes et coûts HT explicites par ligne, prix figés, référence unique, client facultatif, droits et versions, idempotence. Retours revendables réintègrent le stock ; non revendables conservent leur coût en perte. Six tests commerce + huit CRM réussis. Recette Chromium devis→vente avec réponse perdue/reprise→retour, stock 10→8→9, persistance, 1440/768/390 et zéro pageerror réussie. Build TS/Vite réussi. À compléter : import CSV des transactions réelles, liens analytique/demande/CRM et opportunités. Prochaine tâche immédiate : achats fournisseurs et réceptions.

## Lot achats vérifié
Commandes et réceptions partielles avec clôture du solde, coûts HT explicites, historique CRM, droits et transactions atomiques. Cinq tests API réussis (reprise, dépassement, atomicité multiligne, conflit de versions, droits). Chromium : commande 5, réception 2 puis 3, réponse perdue et reprise sans doublon, persistance, 1440/768/390, zéro erreur JS, capture mobile inspectée. Build réussi. Formulaire de retour réinitialisé après succès. Prochaine tâche : rentabilité/assortiment sur ventes confirmées et propositions de réapprovisionnement.

## Lots analyse commerciale, réassort et CSV opérationnel
- Rentabilité : cohorte des ventes confirmées sur période (dates de Tunis), retours connus imputés aux ventes d'origine ; frais externes exclus, coûts absents explicités. Classement par contribution, associations répétées, résumé 90 jours dans le CRM. 3 tests API et Chromium (calcul, période, CRM, 1440/768/390, zéro pageerror) réussis ; capture mobile inspectée.
- Réassort : conditions fournisseur par produit (coût TND HT explicite, délai, minimum, colis, activation) avec historique. Propositions min/max incluent commandes et brouillons, alertent sur retards, appliquent enveloppe et arrondis. Création atomique d'un brouillon, empreinte anti-périmé, idempotence. 5 tests API dont concurrence et Chromium réponse perdue/colis/budget/achat lié réussis ; capture mobile inspectée. Ce sont des règles, pas un optimum de bénéfice ni une prévision ML.
- CSV opérationnel : troisième mode distinct, paniers multilignes, date métier stockée séparément, fiscalité explicite, quantité cumulée vérifiée, lot entier atomique et doublons de référence intersources refusés. 5 tests API + Chromium réponse perdue/reprise/document daté réussis. La demande ML inclut désormais les ventes confirmées nettes des retours, avec invalidation des résultats et semaines inconnues conservées.
- Build TS/Vite réussi après ces intégrations. Régression ciblée de 50 tests réussie ; régression globale en cours.
- Migrations : tables additives replenishment_policies, replenishment_events, commercial_sale_dates ; aucun remplacement de données, recette isolée.
- Prochaine tâche : opportunités commerciales et document imprimable, puis inventaire/alertes/sauvegarde, veille automatisée et mobile. Aucun déploiement ni collecte externe activé à ce stade.

## Lots B2B, maintenance et inventaire vérifiés
- Régression globale du socle et des lots précédents : **130 tests Python réussis**, puis **2 opportunités + 3 maintenance + 3 inventaires** réussis séparément. Avertissement Starlette/httpx connu, non bloquant ; aucune modification de dépendance requise pour ces fonctionnalités.
- Opportunités CRM : étapes, potentiel TTC, échéance, devis du même client uniquement, motif et historique. Gagnée ne crée aucune vente. Devis/vente imprimables en A4, coûts et contribution exclus. Chromium création/modification/lien devis/absence de revenu fictif/1440-768-390 + rendu imprimable vérifiés. `docs/evidence/quote-print.pdf` est une recette synthétique, pas un document fiscal.
- Maintenance : sauvegarde cohérente via API ADMIN ou CLI, manifeste SHA-256, intégrité et références, restauration exclusivement vers nouveau fichier. Tests de restauration réelle d'une vente et son stock, corruption/refus d'écrasement/droits. Récupération CLI sur administrateur actif : confirmation explicite, saisie masquée, expiration des sessions et journal ; aucun compte réel modifié. Guide `docs/MAINTENANCE.md`. Chromium sauvegarde/téléchargement/3 largeurs réussi.
- Inventaire : campagne et sélection, comptage sans mouvement, historique, validation atomique des écarts, conflits après mouvement, recompte, annulation sans ajustement. Trois tests API et Chromium réponse perdue sans doublon + 3 largeurs réussis. Tables additives inventory_sessions/inventory_lines/inventory_events.
- Autres tables additives : crm_opportunities, local_recovery_events. Build TS/Vite réussi après intégration.
- Prochaine tâche immédiate : alertes actionnables, identité canonique et collecte concurrentielle bornée avec planification durable ; puis mobile, recette finale et guide complet.

## Collecte et décisions vérifiées
Le choix utilisateur du scraping de fiches publiques est confirmé. Collecte bornée sans descriptions longues, contrôle robots/DNS public/TLS/redirections, 200 fiches actives maximum, intervalle minimal 6 h et requêtes espacées d’au moins 10 s par enseigne. Le serveur local traite la file persistante ; aucune promesse de fonctionnement PC éteint. Aucun prix interne automatiquement appliqué. Identité canonique et GTIN avec clé, contrôle contradictoire MPN/GTIN, revue humaine des variantes/taxes/livraison ; traces par empreintes, source/date/version du parseur.
38 tests collecte/marché/maintenance réussis, puis 17 collecte/décisions. Chromium collecte/identité/reprise réseau/revue/pause/persistance et décisions/reprise/navigation, 1440/768/390 sans erreur JS. Capture mobile web collecte inspectée.
Sondes réelles du 12 octobre : robots des trois enseignes accessibles ; extraction de prix sur une fiche Spacenet et une Tunisianet ; Mytek retourne HTTP 403. Ces sondes ne sont pas intégrées au catalogue opérationnel et ne prouvent ni couverture exhaustive ni matching automatique.
Mobile : espace commercial en développement (consultations, confirmation de documents, réceptions partielles, comptage/validation, notes CRM, décisions). Régression globale et Android en cours.

## Livraison de recette du 12 octobre — état final

- Serveur web de recette : **http://127.0.0.1:8000**, processus et base dans `runtime/recipe-server.json`. Compte et mot de passe généré dans `runtime/recette-17cec9589e73/ACCES_RECETTE.txt`. Données purement fictives ; aucun compte ou fichier opérationnel modifié.
- Relance : `scripts/run-recipe.ps1` ; nouvelle base sans écrasement : `-New`. Dix écrans vérifiés à 1440 et 390, bandeau de recette, chiffres initiaux du guide contrôlés, zéro pageerror. Capture rentabilité mobile inspectée.
- Python : 155 tests globaux réussis, puis 22 tests ciblés après les deux ajouts de contrôle (157 tests inventoriés, pas 157 exécutés dans un même dernier run). Dépendances cohérentes, Black/contrôle AST et diff vérifiés. Le formatage multiprocessus Windows ne terminait pas ; terminé sans parallélisme. Aucun échec métier résiduel connu.
- TypeScript/Vite compilés ; toutes les recettes métier navigateur décrites ci-dessus réussies. Dernière collecte/revue/reprise et recette complète des écrans réussies après les derniers changements.
- Flutter : analyse sans erreur, 11 tests réussis, deux scénarios Android complets contre API réelle (socle et commercial). Les tests attendent désormais la fin des transitions avant navigation retour. Stocks commerciaux 10 → 8 → 10 → 9 vérifiés. Captures inspectées ; APK normal `lib/main.dart` recompilé après les APK de test, empreinte dans `docs/evidence/native-build.json`.
- Émulateur et serveur QA natif arrêtés ; serveur web de recette conservé. Aucun push, publication, achat ou déploiement distant.

### Avancement estimé et périmètre

**95 % de préparation à la recette locale**, soit 19 lots validés sur 20 lots de livraison : accès, catalogue, mouvements/prix, CRM, opportunités, commerce, retours, CSV, achats/réceptions, réassort, contribution/paniers, demande ML, identité/revue, planification, décisions, inventaires, maintenance, web/mobile, documentation/recette. Le vingtième lot est la vérification d'accès réel aux trois enseignes : Tunisianet et Spacenet extraient un prix ; Mytek renvoie HTTP 403. Le code de cette source et son échec sont testés, mais l'accès réel n'est pas déclaré opérationnel.

Ce pourcentage ne mesure ni une certification de production, ni la qualité prédictive réelle, ni un gain financier garanti. La valorisation/rotation comptable exige une politique de coût et un historique fiable. La causalité des produits d'appel exige une expérimentation commerciale. L'étude exhaustive de tous les acteurs, iOS signé, hébergement HTTPS, SMTP et boutiques restent hors de cette recette locale. Ces limites ne sont pas cachées derrière un bouton ou des données simulées.
