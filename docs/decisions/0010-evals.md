# ADR-0010 — Évals : scénarios TOML, pipeline réel, notation déterministe

- Statut : accepté (2026-11-03)

## Contexte
La spec §14.2 demande au moins 30 scénarios versionnés (10 web/API, 8 Excel, 6 PowerShell, 6 feature, plus des cas adversariaux). Ces scénarios sont distincts des tests de code. Elle demande aussi un rapport JSON/HTML de régression. Un LLM-juge ne remplace ni les tests exécutables ni la revue humaine. La phase 5 exige « aucun faux chiffre ».

## Décision
- **Scénarios en TOML, un fichier par suite** (`evals/datasets/<suite>.toml`, lus avec `tomllib`, sans dépendance). Un cas contient une demande, un type de projet et ses attentes (`[case.expect]`). Une clé inconnue, un type inconnu ou un identifiant en double rend le jeu invalide : la commande s'arrête (code 2) au lieu de mesurer de travers.
- **Le pipeline réel, sans base de données.** `nfactory_worker.evals` appelle `execute_run` avec la vraie recette et le vrai runner (`SandboxRunner` via `scripts/evals.ps1`, ou `LocalRunner`). Le reporter garde ce que la base garderait : des copies passées par `redact`.
  - Un cas « feature » livre d'abord le projet de départ, puis lance la demande d'évolution en run enfant (scénario E).
  - Un cas peut fournir des passages de base de connaissances, pour tester les citations et les sources hostiles.
- **Moteur démo par défaut.** Le moteur est déterministe et gratuit, donc deux versions de NFactory se comparent à entrée égale. Le rapport le dit : il mesure le pipeline, les recettes, les vérifications et les garde-fous, pas la qualité d'un modèle. Comparer des fournisseurs reste la tâche 5.5.
- **Notation déterministe uniquement.** Elle vérifie :
  - le résultat attendu ;
  - la couverture du cahier des charges : entité, champs, fichiers, textes ;
  - le minimum de tests réussis, d'après les rapports JUnit ;
  - l'intégrité des artefacts : sha256 recalculé, archives lisibles, noms sans chemin ;
  - les sources citées ;
  - les commandes : liste autorisée, aucun texte interdit ;
  - le code Python généré : il se parse (AST) et n'appelle rien d'interdit ;
  - les alertes de l'analyse de secrets ;
  - l'absence du secret ;
  - la taille du diff.
  Aucun avis d'agent n'entre dans la note.
- **Secrets factices générés à l'exécution.** Un cas écrit `{secret}`. La commande le remplace par une clé au format réel, créée pour ce run, puis vérifie qu'elle n'apparaît nulle part : ni dans les sorties stockées, ni dans les événements, ni dans les livrables, archives comprises. Le dépôt ne contient donc aucune fausse clé à signaler.
- **Rapport.** `evals/reports/eval-<horodatage>.json`, `.html` et `latest.json`, non versionnés. Chaque chiffre donne sa source. Une mesure absente vaut `null` (« non mesuré »), jamais un 0 inventé. La comparaison se fait avec `latest.json`, ou avec le rapport donné par `--compare`. Elle liste les régressions, les corrections et les nouveaux cas. Un cas ignoré, faute de `pwsh` ou de `node` en local, ne compte pas dans le taux.

## Conséquences
- Les minimums de tests suivent ce que les recettes produisent aujourd'hui : 9 pour l'API et PowerShell, 7 pour Excel, 25 pour l'application web. Une recette qui perd des tests fait échouer l'éval. Une recette qui en gagne doit relever son minimum.
- Une fonctionnalité écrite par Codex dans le dépôt de l'utilisateur n'est pas évaluée automatiquement : il faudrait le compte et l'accord de l'utilisateur. Elle reste testée à la main (tâches 4.3 à 4.7).
- Les résultats ne sont pas encore stockés dans `evaluation_*` ni exposés par l'API (`/evaluations/suites`). Le rapport fichier suffit à la tâche 5.3.
