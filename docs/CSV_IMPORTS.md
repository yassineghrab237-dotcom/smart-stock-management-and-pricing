# Import CSV local

Dans l'application : **Imports CSV**, choisir Catalogue produits ou Historique des ventes, télécharger le modèle, remplir un CSV UTF-8, sélectionner le séparateur puis le fichier. Analyser, examiner les lignes et confirmer l'enregistrement. ADMIN et MANAGER importent ; VIEWER consulte les historiques.

## Catalogue

Colonnes requises : `sku,name`. Facultatives : `category,unit,cost_price,current_price,min_price,threshold_min,threshold_max`.

```csv
sku,name,category,unit,current_price,threshold_min,threshold_max
ARTICLE-001,Article exemple,Accessoires,pièces,12.3456,5,100
```

L'exemple illustre le format et n'est jamais importé automatiquement. Les SKU doivent être uniques dans le fichier et absents du catalogue. Les produits sont créés à stock zéro. Aucun remplacement de produit existant ; utiliser les écrans produit/prix/mouvements pour leurs modifications tracées.

## Ventes historiques

Toutes les colonnes sont requises : `reference,sku,sold_on,quantity,unit_price`.

```csv
reference,sku,sold_on,quantity,unit_price
VENTE-001-LIGNE-1,ARTICLE-001,2025-01-02,3,12.3456
```

`reference` identifie une **ligne de vente unique**, pas nécessairement une facture entière. Elle ne peut pas être réutilisée, même pour un autre SKU. `sku` est rapproché exactement, après retrait des espaces extérieurs, avec le catalogue existant ; la casse reste significative. L'aperçu affiche SKU, nom du produit trouvé, date, quantité et prix. Aucun rapprochement automatique par nom ni identifiant SQLite fourni par le fichier.

Dates au format AAAA-MM-JJ, valides et non futures. Quantités entières positives jusqu'à 2147483647. Prix non négatifs, au maximum quatre décimales, point décimal. Les ventes ne modifient **ni stock actuel, ni prix actuel, ni mouvements** : importer un historique passé ne rejoue pas des sorties déjà comptabilisées. Pour une nouvelle sortie physique, utiliser Mouvements.

## Contrôles et reprise

- Virgule ou point-virgule ; champs contenant le séparateur entourés de guillemets selon CSV. UTF-8 avec ou sans BOM.
- Interface : fichier au maximum 1 000 000 octets ; serveur : texte au maximum 1 000 000 caractères et 1 000 lignes métier. Colonnes inconnues/dupliquées refusées ; lignes entièrement vides ignorées.
- Une ligne invalide bloque l'import entier. L'aperçu n'écrit rien. L'enregistrement revalide dans une transaction SQLite avant toute insertion.
- Un produit modifié depuis l'aperçu ou un fichier modifié exige une nouvelle analyse. Aucune saisie partielle n'est appliquée.
- Le même contenu et séparateur ne sont enregistrés qu'une fois, même si le fichier est renommé. Une réponse perdue après commit peut être réessayée avec le fichier et l'aperçu inchangés. Les références ventes et SKU empêchent également les réimports après modification du fichier.
- Aucun effacement, annulation ou remplacement d'un import existant n'est exposé.

## Stockage et limites

Au démarrage local, `CREATE TABLE IF NOT EXISTS` ajoute `csv_imports` (type, empreinte, nom du fichier, nombre de lignes, auteur/date) et `sales_history` (référence, produit, date, quantité, prix unitaire et import). Les tables existantes sont conservées. Le contenu CSV brut n'est pas conservé ; les lignes validées le sont. Aucun fichier du dossier de démonstration `data/` n'est lu par cet import.

L'écran présente les 100 derniers imports et les 100 dernières ventes. Les autres lignes restent en base. Pagination, corrections historiques, retours/remboursements, devises, clients et facturation ne font pas partie de ce parcours.

L'import prépare un historique métier, mais **n'active pas les recommandations IA** : export vers un corpus ML identifié, traçabilité, entraînement, évaluation hors entraînement et liaison des modèles restent à faire. Les contrôles de format ne certifient pas que les ventes importées sont authentiques.

## Validation

```powershell
& .\.venv-local\Scripts\python.exe -m pytest tests -q
Set-Location frontend
npm.cmd run build
Set-Location ..\tests
npm.cmd run test:imports
```

21 nouveaux cas Python (58 au total) et recette Chromium CSV isolée : doublons refusés, aperçu sans écriture, précision des prix, stock conservé, conflit, reprise réseau après commit, persistance, droits et 390/768/1440 sans overflow. Résultat : `docs/evidence/imports-results.json`. Les tests utilisent des bases QA ; `tests/conftest.py` isole aussi la construction du gateway global lors de la collecte pytest. Le script navigateur CSV utilise le port 8011 et arrête son propre serveur.


## Ventes opérationnelles avec sortie de stock (TND)

Choisir **Ventes avec sortie de stock**. Colonnes requises : `reference,sku,sold_on,quantity,unit_price_ttc,tax_rate`. Facultatives : `discount_ttc,unit_cost_ht,customer_id`. Prix et remise unitaires TTC, coût HT, taxe en pourcentage ; coût vide = contribution inconnue. Client = identifiant CRM local facultatif. Plusieurs SKU distincts avec même référence forment un panier, avec date et client identiques ; maximum 100 produits par vente, 1 000 lignes par fichier.

La date `sold_on` est la date commerciale de Tunis ; l'enregistrement et les mouvements sont horodatés au moment de l'import. L'aperçu affiche le stock avant/après l'ensemble du fichier. La validation recontrôle toutes les lignes et versions puis crée ventes confirmées et sorties dans une transaction unique. Le même fichier renommé n'est pas rejoué ; une référence déjà dans les documents ou l'historique est refusée. Des références différentes pour une même vente ne peuvent pas être détectées automatiquement : ne pas réimporter des sorties déjà comptabilisées.

Ces ventes apparaissent dans Ventes et devis, rentabilité, CRM si associé et demande ML. Les retours suivent ensuite le parcours de retour relié à la vente. L'import historique garde son contrat : aucune modification du stock et aucune marge fiscale calculée sans métadonnées.
