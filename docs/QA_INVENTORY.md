# Inventaire de recette

## Livraison native et analyse — 11 octobre 2026

Résultats courants : **70 tests Python réussis**, `pip check` conforme, TypeScript/Vite compilés ; **8 tests Flutter réussis**, `flutter analyze` sans erreur. Quatre recettes Chromium cœur/design/CSV/livraison réussies avec zéro `pageerror` ; contrôle web des écritures natives également réussi.

| Contrôle nouveau | Preuve |
|---|---|
| Sessions natives séparées, expiration, permissions et HTTP distant refusé | tests/test_mobile_analysis.py |
| Désactivation, réactivation, révocation web/mobile et refus de s’auto-désactiver | tests Python + delivery-browser-results.json ; accounts-390/1440.png |
| Prévision depuis import, quatre semaines hors entraînement, comparaison naïve, semaines manquantes inconnues | tests Python et delivery-browser-results.json ; analysis-390/768/1440.png |
| Job dédupliqué, interruption et résultat périmé caché | tests Python + Chromium ; aucune écriture de stock ou prix |
| Premier accueil et guide français | dashboard-start.png, guide-390/768/1440.png ; absence de débordement |
| HTTPS, formulaire 320/390/768, brouillon persistant après réponse perdue | mobile/test/widget_test.dart, protocole HTTP de test local |
| Rafraîchissement natif et changement d’onglet | mobile/test/refresh_test.dart ; deux régressions sans réutilisation du résultat précédent |
| Parcours Android sur backend réel isolé | mobile/integration_test/app_test.dart : réussi sur émulateur SmartStock_QA ; cinq captures native-*.png |
| Cohérence mobile/web après stock et prix | native-web-results.json, native-web-consistency.png : stock 27, prix 12.3456, exactement deux mouvements après reprise |

La recette Android utilise le vrai `flutter_secure_storage`, un jeton Bearer délivré par FastAPI et une SQLite QA neuve. Elle crée un produit par les écrans Flutter, enregistre une entrée de 20 et un prix, puis simule une réponse perdue après une seconde entrée de 7 déjà appliquée. Un nouveau client relit son brouillon sécurisé et reprend la même clé : le stock reste 27, aucun troisième mouvement. Elle vérifie aussi l’alerte sous 30, le résultat d’analyse avec historique manquant et la révocation du jeton au logout. Ce test de reprise simule la perte de réponse ; ce n’est pas une certification sur opérateur mobile réel.

L’émulateur Android 36.1 a provoqué des redémarrages graphiques avec la version 37.1.11 installée. La recette finale a réussi avec l’autre version déjà installée 36.3.10, navigation à trois boutons et `--no-enable-impeller`. Aucun téléphone personnel modifié. Des ralentissements du rendu logiciel ont été observés ; les performances d’un appareil physique restent à mesurer.

Les captures web guide/analyse/comptes et natives accueil/confirmation/alertes ont été inspectées visuellement : textes, boutons et navigation lisibles, confirmation avant écriture, aucun débordement relevé. La recette iOS et la signature production restent non exécutées sur Windows. La fin de compilation de l’APK normal et son empreinte sont conservées dans `native-build.json`.

Les sections suivantes décrivent aussi les parcours hérités, toujours conservés. Les contrôles ML synthétiques ne valident pas la qualité sur les ventes d’une boutique réelle.

Les tests serveur utilisent exclusivement des SQLite temporaires. La recette navigateur utilise une nouvelle base sous `runtime/browser-qa-*`, des comptes `example.test` et des produits étiquetés Recette. Aucune importation automatique des CSV fictifs dans le stock.

| Parcours / contrôle | Vérification fonctionnelle | Vérification visuelle / preuve |
|---|---|---|
| Premier compte, connexion, déconnexion | setup unique, cookie, session expirée, droits | formulaire lisible et labels |
| Ajouter produit | création puis rechargement et redémarrage backend | dialogue, focus initial, champs facultatifs |
| Recherche, filtre, tri, fiche et retour | contexte liste conservé | table desktop, cartes mobile |
| Entrée/sortie/ajustement | 100 - 15 + 20 = 105, motif, historique | récapitulatif puis confirmation |
| Double soumission / concurrence | idempotence et conflit 409 suivi de reprise explicite | bouton désactivé pendant requête |
| Refus invalides | aucun mouvement écrit, saisie conservée | texte français et quantité excessive |
| Alertes | stock < min ou > max, résolution dérivée | statut texte et action produits |
| Prix | Decimal 4 chiffres, plancher, historique, permissions | valeur actuelle distincte de formulaire, limite ML visible |
| ML | cinq entraînements + six inférences sur données synthétiques isolées | aucune prédiction inventée sur stock opérationnel |
| Comptes lecture seule | lecture permise, écritures API 403 | actions indisponibles |
| Réseau indisponible | erreurs affichées, réessai disponible | aucune fausse notification de succès |
| Session expirée | 401 renvoie à connexion | message explicite |
| Design system | composants des vrais écrans | route réservée au développement |
| Responsive | actions principales à 390/768/1440 | captures et absence débordement horizontal |
| Clavier | focus, Tab, Escape, dialogue | contrôle du focus visible |

Scénarios exploratoires : réponse perdue après mouvement confirmé (même clé de retry), produit modifié simultanément (version périmée), quantité invalide, modèle absent ou non lié, accès direct sans session. Une revue technique et une recette automatisée ne remplacent pas un test avec de vrais utilisateurs.
# Extension CSV — 9 octobre 2026

21 cas supplémentaires dans tests/test_imports.py : aperçu sans écriture, catalogue avec BOM/point-virgule et précision prix, reprises et redémarrage, doublons, validation atomique, dates/quantités/prix invalides, SKU exact, conflit depuis l'aperçu, colonnes/limites, droits/Origin et double commit concurrent. Suite complète : 58 passed.

tests/browser-imports.mjs (port 8011, base runtime/import-qa-* dédiée) : import catalogue et ventes réel, refus doublon, aucune écriture lors de l'aperçu, stock/prix/mouvements préservés, réponse perdue après commit et retry sans doublon, rechargement, VIEWER, Escape/focus et captures 390/768/1440 sans overflow. Zéro pageerror. Preuves : docs/evidence/imports-results.json et imports-{390,768,1440}.png. Les deux recettes navigateur précédentes ont aussi été rejouées avec succès.

tests/conftest.py détourne la construction globale du gateway vers une base bootstrap temporaire avant la collecte pytest ; chaque cas continue à utiliser sa propre base. Aucun fichier de recette supprimé automatiquement.
