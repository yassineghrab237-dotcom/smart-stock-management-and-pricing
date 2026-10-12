# Collecte concurrentielle — fonctionnement et observations

La décision utilisateur du 12 octobre est de collecter les fiches publiques par scraping. Le produit n'impose pas de case déclarant un accord fournisseur inexistant. Il conserve source, date, empreinte de page et de robots, version du parseur et décisions humaines.

## Fonctionnement livré

1. Définir l'identité canonique du produit : marque, référence fabricant, GTIN facultatif avec clé de contrôle, variante/état/garantie.
2. Ajouter une URL HTTPS de fiche Tunisianet, Mytek ou Spacenet, sans paramètres ; intervalle de 6 à 168 h, 24 h par défaut. Maximum 200 fiches actives.
3. Le serveur local prend les jobs dans SQLite. Requêtes espacées d'au moins 10 s par enseigne, délai robots plus long respecté ; limites réseau, taille et redirections ; DNS public et TLS validés. Aucun cookie de compte, CAPTCHA ou contournement d'accès.
4. Extraire les champs structurés JSON-LD ou microdonnées : nom court, prix/devise, disponibilité, MPN/GTIN/code marchand. Ne pas copier descriptions longues et images. Une page ambiguë ou refusée ne produit pas un prix fictif.
5. Valider humainement l'identité, les variantes, taxes et livraison. Les MPN/GTIN contradictoires empêchent l'acceptation ; une identité modifiée depuis la collecte impose un nouveau relevé. MPN absent ne signifie pas matching prouvé. Les GTIN invalides ne sont pas utilisés.
6. L'observation acceptée rejoint l'historique existant. Aucune modification du prix interne. Comparaison seulement si les conditions concordent et si les observations datent de moins de 24 h.

Le worker se lance avec FastAPI ; `SMART_STOCK_COLLECTION=0` le désactive. Pause/reprise des URL, erreurs et prochaines échéances sont persistées. Une tâche abandonnée depuis 20 minutes est marquée interrompue. Reprise manuelle bornée à une demande par 15 minutes ; pas de boucle de retry agressive. Un PC ou serveur éteint ne collecte pas.

## Sondes réelles du 12 octobre 2026

- [Tunisianet robots](https://www.tunisianet.com.tn/robots.txt) accessible. Une fiche a fourni un prix TND ; disponibilité, base fiscale et référence constructeur restent inconnues dans l'extraction de cette page.
- [Mytek robots](https://www.mytek.tn/robots.txt) accessible. La fiche testée a renvoyé **HTTP 403** depuis ce PC ; aucun prix enregistré. L'adaptateur et le traitement des échecs sont testés sur fixtures, mais l'accès réel à cette fiche reste bloqué.
- [Spacenet robots](https://spacenet.tn/robots.txt) accessible. Une fiche a fourni prix TND et stock annoncé. Code marchand présent, MPN absent ; validation nécessaire.
- Preuves locales : `evidence/collection-live-probe.json` et `collection-live-probe-more.json`. Ces constats sont datés, ne sont pas un SLA et n'ont pas alimenté le stock opérationnel.

Les conditions publiques consultées sont conservées comme contexte ([Tunisianet](https://www.tunisianet.com.tn/content/3-conditions-generales-de-ventes), [Mytek](https://www.mytek.tn/conditions-generales-de-vente), [Spacenet](https://spacenet.tn/content/3-terms-and-conditions-of-use)). La lecture de robots n'est pas une certification juridique. Référence technique des règles de chemin : [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html).

Aucune étude exhaustive du marché ni inférence des ventes concurrentes à partir de leur disponibilité. La liste de fiches suivies doit correspondre au catalogue réel de l'utilisateur.
