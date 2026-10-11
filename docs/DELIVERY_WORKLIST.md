# Finalisation locale — 11 octobre 2026

Priorités déduites du produit existant et de la demande mobile. Aucun déploiement, achat ou envoi externe.

| Priorité | Travail | Critère de validation |
|---|---|---|
| P0 | Session native indépendante | Jeton haché serveur, stockage sécurisé mobile, expiration/revocation et rôles testés ; cookies web inchangés |
| P0 | Application Flutter Android/iOS | Connexion, accueil, recherche produit, mouvements confirmés, prix, alertes, historique et paramètres reliés aux vraies API |
| P0 | Réseau et doubles envois | Aucun succès avant réponse ; clé conservée après échec, reprise après redémarrage, conflit revalidé |
| P1 | Accueil web orienté tâches | Premiers pas sans données, actions stock/import/analyse, statut IA clair, guide accessible |
| P1 | Analyse de l'historique importé | Travail suivi jusqu'au résultat, données provenance import, validation chronologique, aucun prix appliqué automatiquement |
| P1 | Guide Commencer en 5 minutes | Noms exacts des boutons, exemple concret, utilisation mobile, dépannage et captures réelles |
| P0 | Recette | Tests HTTP et Flutter, build web et APK si outils/licences disponibles, browser QA, contrôle des données originales |

Limites externes : compilation/signature iOS sur macOS/Xcode ; diffusion mobile ou backend HTTPS distant non autorisée ; aucun historique réel ni SMTP fourni. Ces limites ne bloquent pas le code et les parcours locaux.

## Résultat de cette livraison

Les lignes ci-dessus sont réalisées localement : 70 tests serveur, 8 tests Flutter, compilation web, recette Android complète avec le backend réel, quatre recettes Chromium et cohérence des écritures native/web. Le guide utilisateur et le guide technique sont distincts. La gestion de comptes permet également désactivation/réactivation et révocation web/mobile confirmées. Les preuves et les limites actuelles sont dans PROJECT_STATE.md et QA_INVENTORY.md.

Le code iOS est fourni mais sa compilation reste une étape externe sur Mac. Les anciens modèles de tarification ne sont pas qualifiés pour les ventes réelles. Cette livraison ne constitue ni un déploiement ni une certification de production.
