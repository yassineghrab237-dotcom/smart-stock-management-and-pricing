# Inventaire de recette

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
