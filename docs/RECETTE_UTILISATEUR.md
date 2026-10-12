# Recette utilisateur — Precios

## Accès et démarrage

Depuis la racine du dépôt : `powershell -File .\scripts\run-recipe.ps1`. Ouvrir **http://127.0.0.1:8000**. Le script indique le fichier `runtime/recette-…/ACCES_RECETTE.txt` contenant le compte et le mot de passe généré. Le pointeur `runtime/latest-recipe.json` retrouve la base courante. Utiliser `-New` pour une autre recette ; aucune base précédente n'est effacée.

Un bandeau indique « Environnement de recette · données fictives ». Ne pas y saisir vos données réelles. La base opérationnelle `runtime/stock.sqlite3` reste distincte. Arrêter le serveur avec Ctrl+C ; les essais sont conservés dans la base de recette.

## Parcours à essayer

| Parcours | Actions | Résultat attendu |
|---|---|---|
| Accueil et catalogue | Se connecter, ouvrir Produits et stock, rechercher DEMO-PC | Trois références fictives ; PC 10, souris 23, câble 3 au départ |
| Devis entreprise | Ventes et devis → DEMO-DEVIS-001 → convertir, nouvelle référence unique | Vente de 2 PC ; stock PC 10 → 8, devis converti et historique conservé |
| Retour client | Sur cette vente, retourner 1 PC revendable avec motif | Stock 8 → 9 ; montant net et contribution ajustés |
| Retour abîmé | Retourner l'autre PC comme non revendable | Stock reste 9 ; coût conservé en perte dans l'analyse |
| Réception partielle | Achats → DEMO-ACHAT-001 → réceptionner 4 souris | Stock souris 23 → 27 ; 6 encore attendues ; aucune double entrée après reprise réseau |
| Réassort | Ouvrir Réapprovisionnement ; câble DEMO-USB, conditions présentes | Besoin 27 arrondi à 30 par colis de 5 ; coût 120 TND HT ; budget inférieur à 120 exclut cette ligne |
| Brouillon d'achat | Avec budget suffisant, préparer le brouillon du câble | Le stock reste 3 ; le brouillon entre dans les engagements et empêche une nouvelle proposition identique |
| CRM | Client démo entreprise → note, tâche, opportunité et devis lié | Historique visible ; gagner l'opportunité ne crée aucune vente |
| Rentabilité | Ouvrir Rentabilité et paniers avant vos modifications | Deux ventes ; TTC 2 451,40 ; HT 2 060,00 ; contribution HT 464,00 ; PC et souris associés dans 2 paniers |
| Inventaire | Comptage démo du rayon → saisir quantités actuelles, câble compté 2 → valider | Comptage seul sans effet ; validation ajuste le câble 3 → 2 avec motif |
| Décisions | Alertes → achat en retard ou tâche → mettre en cours avec motif | Suivi historisé ; la condition reste visible tant que sa cause persiste |
| Veille | Choisir un produit, renseigner référence constructeur et variante, ajouter une URL publique équivalente | Job enregistré ; actualiser après quelques instants ; extraction candidate ou message d'échec explicite |
| Validation de veille | Vérifier source, référence, RAM/stockage, état, garantie, taxes et livraison, accepter ou refuser | Offre acceptée historisée ; refus tracé ; contradictions MPN/GTIN bloquent l'acceptation |
| Comparaison | Deux enseignes, mêmes identité/variante/devise/taxes, livraison connue, stock annoncé et relevés <24 h | Prix total comparé ; sinon comparaison indisponible avec données conservées |
| CSV | Imports CSV → transactions ; aperçu avant validation | Panier confirmé et stock réduit une seule fois ; historique de ventes reste un mode séparé sans mouvement |
| Sauvegarde | Sauvegarde et reprise → créer puis télécharger base + manifeste | Fichiers récupérables ; restauration CLI vers nouveau fichier uniquement, voir MAINTENANCE.md |
| Lecteur | Créer un compte VIEWER depuis Collaborateurs, se connecter avec lui | Consultation possible, écritures masquées et refusées côté serveur |
| Mobile | Android → Plus → Espace commercial | Même base : consultations, confirmations, réceptions, comptages et notes ; aucune file d'envoi automatique hors ligne |

Les chiffres du tableau supposent de partir d'une recette neuve et de respecter l'ordre des étapes liées. Les prix et clients démo sont fictifs. Aucune URL de concurrence n'est activée automatiquement par le générateur de recette.

## Reprise après erreur

Une écriture avec réponse perdue doit être réessayée avec les mêmes valeurs pour réutiliser sa clé. Un conflit de version demande d'actualiser et de vérifier le résultat avant une nouvelle décision. Sur Android, le brouillon sécurisé est accessible depuis l'accueil ; ne pas recréer aveuglément la même opération.

## Limites visibles

Mytek a renvoyé HTTP 403 lors de la sonde réelle du 12 octobre : l'outil signale l'échec. Les deux autres sondes ont extrait un prix, mais cela ne prouve pas la correspondance avec votre catalogue. La collecte suit les seules URL configurées, tant que le serveur tourne ; elle ne couvre pas tous les acteurs du marché. Un stock affiché chez un concurrent ne révèle pas ses ventes.

Contribution = ventes nettes HT moins coûts connus, hors frais externes. Les associations de panier ne prouvent pas un effet d'appel. La demande ML exige assez de semaines consécutives connues ; la démo commerciale courte n'est pas un historique suffisant. Aucun LLM externe ni clé API n'est nécessaire.

## Commandes de contrôle

```powershell
.\scripts\test.ps1
npm.cmd run test --prefix tests
npm.cmd run test:collection --prefix tests
npm.cmd run test:actions --prefix tests
```

Pour le mobile, suivre `MOBILE_INSTALLATION.md`. Le serveur de recette natif `tests/mobile_server.py` utilise encore une autre base neuve sur le port 8012. Ne pas confondre cette base avec celle de vos essais web.
