# Installation technique — web et application native

Le client Flutter partage son code Dart entre Android et iOS et appelle les mêmes API que le web. Il n’embarque pas le site dans une WebView. L’installation locale Android ne rend pas le service accessible depuis Internet.

## Service sur Windows

Depuis la racine du dépôt :

```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

Créer le premier compte sur `http://127.0.0.1:8000`. La base opérationnelle est `runtime/stock.sqlite3`. Arrêter avec Ctrl+C. Si PowerShell refuse les scripts, les commandes manuelles du README évitent de changer la politique globale.

## Compiler Android

Outils vérifiés sur ce PC : Flutter 3.38.4 / Dart 3.10.3, Android SDK et Java 21. Installer les outils manquants et examiner leurs licences ; le projet ne les accepte pas automatiquement.

```powershell
Set-Location mobile
flutter pub get
flutter analyze
flutter test --dart-define=ALLOW_LOCAL_HTTP=true
flutter build apk --debug --dart-define=ALLOW_LOCAL_HTTP=true --dart-define=API_URL=http://127.0.0.1:8000
```

APK attendu : `mobile/build/app/outputs/flutter-apk/app-debug.apk` depuis la racine. C’est une compilation de débogage, signée par la clé de développement, destinée à une installation locale. Aucun APK de production ou compte boutique n’est configuré. La variante release ne reprend pas automatiquement cette clé.

## Connecter votre Android par USB

Activer volontairement le débogage USB sur votre téléphone et autoriser ce PC. Les commandes suivantes sont à exécuter par vous sur l’appareil choisi ; aucune installation n’a été faite sur votre téléphone pendant la recette.

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices
# Remplacer ID_APPAREIL par l’identifiant affiché pour votre appareil.
& $adb -s ID_APPAREIL reverse tcp:8000 tcp:8000
& $adb -s ID_APPAREIL install -r 'mobile/build/app/outputs/flutter-apk/app-debug.apk'
```

Ces commandes d’installation sont données depuis la racine du dépôt. Si vous êtes dans `mobile`, utilisez `build/app/outputs/flutter-apk/app-debug.apk`.

Ouvrir **Smart Stock**. Adresse du service : `http://127.0.0.1:8000`. Utiliser votre compte web. Garder le service et le câble actifs. Refaire le tunnel après déconnexion USB ou redémarrage. Une adresse IP du PC en Wi-Fi n’est pas prise en charge dans cette livraison locale : le backend reste sur loopback et le client refuse HTTP distant.

## iOS sur Mac

Les sources et la configuration iOS sont présentes, y compris le stockage Keychain. La compilation, le simulateur, la signature et la recette iOS restent à exécuter sur macOS avec Xcode ; ce PC Windows ne les permet pas. Ne pas interpréter la présence du dossier iOS comme une compilation réussie. Voir [la procédure officielle Flutter](https://docs.flutter.dev/deployment/ios).

Sur un Mac préparé, depuis `mobile` :

```bash
flutter pub get
flutter analyze
flutter test --dart-define=ALLOW_LOCAL_HTTP=true
flutter build ios --simulator
open ios/Runner.xcworkspace
```

Configurer l’équipe et l’identité définitive dans Xcode avant installation physique. Vérifier la capacité Keychain Sharing et le fichier `Runner/Runner.entitlements`, raccordé aux trois configurations. Le plugin demande cette capacité : [documentation de flutter_secure_storage 10.0.0](https://pub.dev/packages/flutter_secure_storage/versions/10.0.0). Pour un appareil physique, fournir une adresse HTTPS réellement déployée et autorisée ; aucune exception ATS globale n’est ajoutée. Le tunnel USB Android ne s’applique pas à iOS.

## Sécurité, réseau et limites

- Jeton mobile aléatoire valable 12 heures, haché dans SQLite ; mot de passe jamais conservé par le client. Stockage sécurisé Android/Keychain iOS, sauvegarde Android désactivée.
- Les sessions mobiles sont indépendantes des cookies web. Un administrateur peut désactiver le compte ou révoquer toutes ses sessions depuis **Collaborateurs**.
- HTTPS requis, sauf HTTP loopback explicitement activé pour le test Android USB. Aucun contournement TLS ni redirection avec jeton.
- Délai réseau maximal de 25 secondes ; erreur visible et réessai manuel. Les mouvements/prix sauvegardent un brouillon et sa clé avant envoi ; après erreur, la reprise conserve la même requête. Aucun envoi automatique hors ligne.
- Le mobile expose catalogue, mouvements, prix, alertes, historiques et analyse. Imports CSV, seuils détaillés et gestion des comptes se font sur le web. Pas de notifications push, email de récupération ou synchronisation cloud.
- L’analyse est un calcul Python local, sans appel LLM ni tokens. Le résultat est persisté ; une tâche inactive depuis dix minutes est signalée interrompue. Ce n’est pas une file de travaux durable, ni une validation de qualité prédictive sur vos ventes réelles.

## Reproduire la recette native

`tests/mobile_server.py` crée toujours une SQLite QA neuve sur le port 8012. Ne pas utiliser ce serveur pour vos données. Démarrer un émulateur dédié, puis, dans un autre terminal :

```powershell
.\.venv-local\Scripts\python.exe tests/mobile_server.py
# Autre terminal, depuis mobile :
flutter drive --no-enable-impeller --driver=test_driver/integration.dart --target=integration_test/app_test.dart -d ID_EMULATEUR --dart-define=ALLOW_LOCAL_HTTP=true --dart-define=API_URL=http://127.0.0.1:8012
```

Configurer aussi `adb -s ID_EMULATEUR reverse tcp:8012 tcp:8012`. Le test crée uniquement des produits QA et écrit ses captures sous `docs/evidence`. Redémarrer un serveur QA neuf avant une nouvelle recette complète. La compilation de ce test remplace temporairement l’APK debug : reconstruire ensuite l’APK normal avec `flutter build apk --debug ...` avant livraison.
## Extension commerciale du 12 octobre

Dans **Plus → Espace commercial**, le natif consulte les ventes/devis, achats, contacts, inventaires, contributions, décisions et observations concurrentes. Il confirme les documents commerciaux déjà préparés, réceptionne une ligne fournisseur partiellement, compte puis valide un inventaire, ajoute des notes CRM, termine une tâche et prend en charge une décision. Toutes ces écritures utilisent le même brouillon sécurisé avec clé idempotente et confirmation explicite.

Création des documents multilignes, retours, configuration du réassort, collecte/revue des variantes, CSV, collaborateurs et sauvegardes se font sur le web. Les prix de veille natifs sont en consultation. Pas de parité intégrale de formulaires entre les deux interfaces.

Scénario commercial Android supplémentaire :

```powershell
flutter drive --no-pub --no-enable-impeller --driver=test_driver/integration.dart --target=integration_test/business_test.dart -d ID_EMULATEUR --dart-define=ALLOW_LOCAL_HTTP=true --dart-define=API_URL=http://127.0.0.1:8012
```

Démarrer un `tests/mobile_server.py` neuf pour chaque scénario complet. Le test crée des données fictives via les mêmes API, puis vérifie les actions UI et les stocks côté serveur. Reconstruire ensuite l'APK normal, car `flutter drive` produit un APK de test.
