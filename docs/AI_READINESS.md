# Audit de préparation aux agents IA

Date : 9 octobre 2026. Source : dépôt cloné depuis GitHub, commit `5b60a03` (`Premier commit`). Les sections initiales ci-dessous décrivent le premier audit documentaire. L'implémentation et les preuves ultérieures sont dans [PROJECT_STATE.md](PROJECT_STATE.md).

## Actualisation après reprise

Au 11 octobre 2026 : client natif Flutter organisé en écrans/services/modèles/widgets, verrous npm/Python/Dart, guide utilisateur séparé du guide technique, analyse de demande sur ventes SQLite et gestion des accès web/mobile. Les nouvelles routes et limites sont dans PROJECT_MAP.md ; les résultats vérifiés courants sont dans PROJECT_STATE.md. Les tableaux d’audit ci-dessous restent historiques et ne décrivent pas l’état actuel des tests ou dépendances.

Le cœur Auth/Stock/Alerts/Gateway a été implémenté avec persistance SQLite ; un frontend React/TypeScript, des dépendances verrouillées, des tests et des captures sont maintenant livrés. Les deux services ML sont conservés et vérifiés sur des CSV synthétiques isolés. Les limites de données réelles, qualité ML et production restent explicites.

Correction du premier inventaire : **40 modèles joblib historiques sont bien suivis dans Git**. La première conclusion de leur absence était incorrecte. Ils sont conservés, jamais chargés pendant la recette ; les nouveaux artefacts contrôlent leur intégrité et leur correspondance aux données. Les chiffres et constats suivants sont des observations du dépôt initial, pas son état courant.

## Verdict

Le dépôt initial était insuffisamment documenté pour qu'un agent IA puisse travailler de manière fiable : aucun Markdown métier, aucune instruction d'agent, aucune carte, aucun guide de démarrage. Les noms des services pouvaient laisser croire à des fonctions actives alors que la plupart des fichiers sont vides.

Les ajouts locaux rendent maintenant le projet navigable et explicitent ses limites. Ils ne rendent pas l'application prête pour la production et ne remplacent pas des tests fonctionnels.

## Constats vérifiables

| Critère | État initial | Après cet audit |
|---|---|---|
| README de racine | absent | guide, état réel, commandes et limites ajoutés |
| Instructions `AGENTS.md` | absentes | règles de modification, validation et sécurité ajoutées |
| Carte architecture / données / routes | absente | `PROJECT_MAP.md` ajouté |
| Dépendances reproductibles | 7 requirements vides | versions observées documentées ; verrouillage encore à réaliser |
| Tests / CI | aucun trouvé hors `.venv` | aucun test fonctionnel ajouté dans cet audit documentaire |
| Services actifs identifiables | peu clair | 2 implémentés et 5 squelettes distingués |
| Environnement portable | `.venv` d'un autre PC versionné | création d'un environnement local expliquée |
| Chemins entraînement/inférence | artefacts séparés par défaut | variables communes documentées ; code inchangé |
| Sécurité d'accès | routes ML sans protection trouvée | limite signalée ; protection à implémenter |

144 fichiers Python dans `libs` et `services`, dont 110 vides et 34 non vides. Les deux services ML contiennent respectivement 14 et 20 fichiers Python non vides. Le dépôt suit 11 770 fichiers sous `.venv`, sur 12 032 fichiers initiaux : cela rend les recherches globales très bruyantes.

Les métadonnées indiquent Python 3.11.9 et un chemin d'installation sur un autre poste. Les bibliothèques principales observées sont FastAPI, Uvicorn, Pydantic, pandas, NumPy, scikit-learn, joblib et python-dotenv. Aucun fichier de dépendances opérationnel ne les déclare actuellement.

## Priorités suivantes

1. Déclarer les dépendances des deux services ML dans leurs manifests et valider une installation neuve. Choisir ensuite une stratégie de verrouillage.
2. Ajouter des tests utiles : routes, données absentes/invalides, produit inconnu, modèle absent, cohérence entraînement/inférence et fallback explicite.
3. Uniformiser la configuration des artefacts et des variables d'environnement dans le code, avec erreurs explicites.
4. Protéger les routes, notamment les entraînements, puis cadrer les permissions et la provenance des modèles.
5. Nettoyer le versionnement du `.venv` et traiter `.env.txt` après revue et autorisation. Aucun fichier existant n'a été supprimé ou modifié pendant cet audit.
6. Implémenter les services métier et un client UX avant de qualifier l'ensemble de produit opérationnel.

Ces éléments sont des travaux proposés, pas des corrections déjà réalisées. Ne pas conclure à une fuite de secrets à partir du seul nom `.env.txt` : son contenu n'a pas été affiché ni audité ici.

## Validation

La copie Git s'est terminée avec succès et le dépôt était propre avant les ajouts. Les routes, chemins et chiffres ci-dessus ont été relevés dans les sources et l'arborescence Git. Le constat initial sur l'absence de modèles a été corrigé dans l'actualisation ci-dessus.

Contrôles exécutés avec l'interpréteur Python local fourni par Codex, sans utiliser le `.venv` du dépôt :

- Analyse syntaxique `ast.parse` : 144 fichiers Python valides, dont 110 vides. Aucune importation du code métier ni écriture de bytecode.
- Documentation : 4 fichiers Markdown, 8 liens locaux vérifiés et blocs de code fermés.
- `git diff --check` : aucune erreur sur les différences suivies. Les nouveaux fichiers non suivis ont été contrôlés séparément pour les liens et la structure Markdown.
- `git status --short` : seuls `README.md`, `AGENTS.md` et `docs/` apparaissent comme ajouts ; aucun fichier existant modifié.

Non exécutés : installation des dépendances, imports des applications, démarrage HTTP, entraînement, prédictions et évaluation des modèles. Les commandes du README sont un guide de validation à suivre, pas la preuve d'une exécution réussie.
