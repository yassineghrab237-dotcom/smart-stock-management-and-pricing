# Sauvegarde et reprise locale de Precios

Ces opérations concernent la base SQLite locale. Elles ne publient rien et ne touchent ni Supabase ni un serveur distant. Sauvegardez aussi séparément le projet, ses manifests et les éventuels modèles entraînés. Les sauvegardes SQLite contiennent les comptes, sessions et données commerciales ; elles ne sont pas chiffrées et doivent rester dans un emplacement protégé.

## Depuis l'application

Un administrateur ouvre **Sauvegardes locales → Créer une sauvegarde vérifiée**. La copie se trouve dans le sous-dossier `backups` à côté de la base active. Télécharger **la base SQLite et son manifeste JSON** et les conserver ensemble. Une copie sur un autre support est nécessaire pour se protéger d'une panne de disque. Aucun ancien fichier n'est effacé automatiquement.

Vérification : intégrité SQLite, clés étrangères, comptages de tables et SHA-256. L'empreinte détecte une modification accidentelle ; ce n'est pas une signature contre quelqu'un qui peut modifier également le manifeste.

## Commandes PowerShell depuis la racine du projet

Exemples de chemins à adapter. Toutes les destinations doivent être nouvelles ; une cible déjà présente est refusée.

```powershell
# Créer une copie cohérente, même lorsque l'application utilise la base.
& .\.venv-local\Scripts\python.exe -m scripts.maintenance backup --source 'runtime/stock.sqlite3' --destination 'runtime/backups/manuel-2026-10-12.sqlite3'

# Contrôler la copie et son manifeste adjacent .sqlite3.manifest.json.
& .\.venv-local\Scripts\python.exe -m scripts.maintenance verify --source 'runtime/backups/manuel-2026-10-12.sqlite3'

# Restaurer dans une base DISTINCTE ; aucune base existante n'est écrasée.
& .\.venv-local\Scripts\python.exe -m scripts.maintenance restore-copy --source 'runtime/backups/manuel-2026-10-12.sqlite3' --destination 'runtime/restauration-essai.sqlite3'

# Ouvrir la copie sur un port distinct pour vérifier comptes, ventes et stock.
.\scripts\run.ps1 -Database 'runtime/restauration-essai.sqlite3' -Port 8029
```

La restauration conserve les comptes et les sessions de la sauvegarde. Connectez-vous avec le mot de passe valable à sa création. Ne considérez pas la copie comme validée pour votre activité avant d'avoir vérifié les dernières ventes, réceptions et quantités attendues. Le programme ne bascule jamais automatiquement l'application sur la copie. Un fichier partiel après panne est conservé pour diagnostic ; son absence de manifeste valide le rend inutilisable comme sauvegarde vérifiée.

## Récupération d'accès administrateur

Réservée au propriétaire autorisé du fichier local. Cette commande remplace le mot de passe d'un administrateur **déjà actif**, expire ses sessions web/mobile et trace un motif en base. Elle ne crée pas de compte et ne réactive pas un compte désactivé. Aucun mot de passe n'est transmis à une API, ni accepté sur la ligne de commande.

Arrêter le serveur concerné avant la récupération et disposer d'une sauvegarde. L'option `--confirm-reset` est l'autorisation explicite de remplacer le mot de passe de ce compte.

```powershell
& .\.venv-local\Scripts\python.exe -m scripts.maintenance recover-admin --database 'runtime/stock.sqlite3' --email 'votre-administrateur@exemple.tn' --reason 'Mot de passe perdu, récupération par le propriétaire' --confirm-reset
```

Le terminal demande deux fois le nouveau mot de passe sans l'afficher : 12 à 256 caractères, avec majuscule et chiffre. Si des tentatives échouées ont déclenché le blocage de connexion, attendre la fin des 15 minutes ; la récupération ne contourne pas le contrôle de fréquence. Les données de stock/vente restent conservées.

## Preuves locales

`tests/test_maintenance.py` vérifie sauvegarde/restauration d'une base synthétique avec vente, refus d'écraser l'original, corruption détectée, API réservée ADMIN, récupération et invalidation de session. Aucun mot de passe ou fichier de données réel n'a été changé pour ces tests.
