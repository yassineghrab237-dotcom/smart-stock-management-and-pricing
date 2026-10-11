# Smart Stock — application native

Client Flutter Android/iOS partageant les API et données de l’application web. Code dans `lib/screens`, `lib/services`, `lib/models` et `lib/widgets`.

## Démarrage

Voir [le guide technique complet](../docs/MOBILE_INSTALLATION.md) et [le guide d’utilisation](../docs/COMMENCER_EN_5_MINUTES.md).

```powershell
flutter pub get
flutter analyze
flutter test --dart-define=ALLOW_LOCAL_HTTP=true
flutter build apk --debug --dart-define=ALLOW_LOCAL_HTTP=true --dart-define=API_URL=http://127.0.0.1:8000
```

HTTP distant refusé. Le mode local exige un tunnel USB Android vers le backend loopback. Sans ce mode, utiliser une adresse HTTPS réellement déployée.

Pas de clé de production, compte boutique ou notification push configuré. Les sources iOS requièrent une compilation et recette sur Mac/Xcode. Ne pas livrer l’APK produit par `flutter drive` : reconstruire l’entrée normale `lib/main.dart` après la recette.
