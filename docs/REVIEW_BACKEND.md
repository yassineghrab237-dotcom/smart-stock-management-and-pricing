# Revue distincte du backend local

Passe effectuée le 9 octobre 2026 après implémentation du cœur. Relecture des sources Auth, Stock, Alerts, Gateway et des tests HTTP du dépôt. Cette passe est **statique** : elle ne constitue pas une nouvelle exécution de la suite HTTP. Les résultats de recette sont conservés séparément par la session principale.

## Constats à corriger

| Priorité | Constat vérifié dans les sources | Conséquence et correction proposée |
|---|---|---|
| P1 | Dans `services/api_gateway/app/main.py`, l'origine est comparée à `request.base_url`, construite à partir de l'en-tête Host. Aucun filtre des hôtes n'est installé au moment de cette revue. | Un Host externe accompagné de la même Origin satisfait le contrôle. Dans un scénario DNS rebinding vers le serveur local, cela compromet notamment la configuration initiale. Ajouter `TrustedHostMiddleware` avec `127.0.0.1`, `localhost` et `testserver`, sans wildcard. Vérifier le refus d'un Host externe même lorsque Origin correspond. |
| P2 | Les paramètres produit des routes et `MovementInput.product_id` n'ont pas de borne supérieure. Le driver SQLite refuse les entiers au-delà de son entier signé 64 bits, tandis que le handler existant ne couvre que `sqlite3.OperationalError`. | Un identifiant supérieur à `9223372036854775807` peut produire une erreur serveur. Borner les identifiants Path/Query/body, ou centraliser une validation métier avant tout bind SQLite. Ajouter une régression HTTP démontrant le rejet sans écriture. |

Le second constat comporte une reproduction isolée réellement exécutée avec la bibliothèque standard : `sqlite3.connect(':memory:').execute('SELECT ?', (9223372036854775808,))` lève `OverflowError: Python int too large to convert to SQLite INTEGER`. Aucune base opérationnelle n'a été utilisée. Le scénario HTTP complet reste à tester.

Ces constats décrivent l'instant de revue avant corrections de la session principale ; vérifier le diff final avant de les présenter comme des défauts encore ouverts.

## Résolution après revue

Les deux constats ont été corrigés par la session principale : TrustedHostMiddleware avec hôtes explicites, et bornes int64 sur les paramètres produit et schémas de requête. Les tests HTTP `test_dns_rebinding_host_refused` et `test_oversized_identifiers_are_validation_errors` passent. Les setups concurrents, plafonds de stock, prix non finis/trop précis et droits MANAGER ont également leurs régressions. Cette validation ultérieure est distincte de la passe statique ci-dessus ; voir PROJECT_STATE.md et docs/evidence/pytest-results.xml.

## Protections observées et limites de leur preuve

- **Configuration initiale** : lecture du nombre d'utilisateurs et création de l'administrateur dans le même `BEGIN IMMEDIATE`. Deux setups concurrents ne peuvent pas créer deux premiers administrateurs par les routes présentes. La course doit encore faire l'objet d'un test HTTP ciblé.
- **Authentification** : mot de passe de création entre 12 et 256 caractères, PBKDF2-SHA256 à 600 000 tours avec sel aléatoire ; sessions hachées, durée de 12 heures, révocation du jeton courant à la déconnexion. Le cookie est HttpOnly/SameSite Strict et Secure lorsque la requête est HTTPS. Il n'existe pas de parcours de changement de mot de passe, de désactivation utilisateur ni de révocation globale : durcissement futur, pas une fonctionnalité prétendument livrée.
- **Concurrence** : mouvements et changements de prix ont une transaction exclusive, une version attendue et une clé d'idempotence liée à l'acteur et au payload. La réponse déjà persistée est vérifiée avant la version, permettant la reprise après une réponse réseau perdue.
- **Quantités** : le schéma refuse les booléens, flottants et chaînes comme entiers. Quantité et stock résultant sont limités à `2147483647`. Des entrées répétées ne peuvent donc pas dépasser cette borne ; une régression au voisinage de la borne est utile. Le total dashboard utilise un `SUM` SQLite ; un dépassement signé 64 bits nécessiterait plus de quatre milliards de produits au stock maximal et ne constitue pas un blocage réaliste du périmètre local.
- **Prix** : Decimal, valeurs finies, non négatives, plafond `999999999999.9999`, quatre décimales maximum, sortie quantifiée sans float. Le prix minimum est vérifié à la création, au patch des métadonnées par validation fusionnée et lors de l'application d'un prix. Aucun plancher basé sur les coûts ni devise n'est inventé.
- **Historique** : aucune route ne modifie ni ne supprime les mouvements ou l'historique tarifaire. La protection append-only concerne les API, pas une personne ayant accès direct au fichier SQLite. Les noms de produits et acteurs de l'historique sont résolus par jointures courantes ; ils ne sont pas des snapshots historiques des noms.
- **Stock négatif** : refus serveur des sorties excessives, contrôle du résultat avant insertion, rollback sur exception. Les ajustements enregistrent la cible ainsi que le stock avant/après.

## Vérifications complémentaires utiles

La suite relue couvre déjà les opérations 100 − 15 + 20, les reprises idempotentes, un conflit concurrent, les refus sans écriture, les alertes, les droits VIEWER, l'expiration de session, les prix/historiques et le minimum. Ajouter en priorité les deux régressions des constats P1/P2, puis une course de setup, le rôle MANAGER, les prix NaN/Infinity/précision excessive, le patch de plancher incompatible et la borne de stock. Ces propositions ne sont pas des tests annoncés comme exécutés.

## Périmètre restant explicite

Le cœur opérationnel utilise SQLite local séparément des CSV de démonstration. L'inférence historique sur CSV et modèles fictifs n'est pas une recommandation validée sur ces produits opérationnels. Une réponse ML `unavailable` ne clôt pas une fonction ML engagée. Aucune activation email, organisation multi-tenant, sauvegarde/restauration vérifiée, exploitation distante ou publication n'est apportée par ce cœur.
