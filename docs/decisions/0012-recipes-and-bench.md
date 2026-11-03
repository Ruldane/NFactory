# ADR-0012 — Recettes réutilisables et comparaison des moteurs

- Statut : accepté (2026-11-03)

## Contexte
La spec demande deux choses en phase 5.
- F38 : « sauvegarder un workflow comme recette réutilisable par l'équipe », avec une recette rejouable comme critère.
- F35 : un « benchmark comparatif des providers sur mêmes tâches, métriques transparentes ».

Une `TemplateVersion` existe déjà. Elle décrit les modèles « golden path » globaux, versionnés et vérifiés par somme de contrôle. Ce n'est pas ce qu'une équipe enregistre elle-même. Les évals (ADR-0010) font déjà tourner le vrai pipeline sur des cas versionnés, mais avec le seul moteur démo.

## Décision
- **Une recette est une ligne de l'espace de travail** (`saved_recipes`, migration `c4d7a2e8f513`). Elle garde ce qu'il faut pour refaire le run : type de projet, recette d'usine (`template_id`), demande et description. Elle garde aussi son run d'origine et son nombre d'utilisations. Elle ne garde ni moteur ni limites : une relance prend ceux du moment, comme n'importe quel run neuf.
- **Créer une recette.** Elle vient d'un run livré de l'espace (`COMPLETED`, sinon 409 `run_not_delivered`), ou elle est écrite à la main (type + demande). L'un ou l'autre, jamais les deux (422).
- **Relancer une recette** (`POST /saved-recipes/{id}/launch`) crée un nouveau projet, puis lance un run par `runs.launch_run`. Budget, moteurs figés, file et refus (`no_model_configured`…) sont donc ceux de tout lancement. La clé d'idempotence est rattachée à la recette, et non au projet créé : un double clic ne fait ni deux projets ni deux runs.
- Enregistrer, relancer et supprimer demandent la permission `build` (ADR-0011) et sont audités (`recipe.save`, `recipe.launch`, `recipe.delete`).
- **« Rejouable », prouvé sur le vrai pipeline.** `tests/evals/test_replay.py` fait passer deux fois la même demande dans `execute_run`. Tous les fichiers générés sont identiques à l'octet près, sauf ceux qui contiennent une horloge : la date de création du classeur et les durées JUnit. Ces deux fichiers sont comparés par contenu (cellules, cas de test).
- **Banc d'essai des moteurs : les évals avec `--engine`, répétable.** `demo` est le moteur par défaut. Les autres s'écrivent `<fournisseur>:<modèle>`.
  - Un moteur réel doit être une connexion que l'utilisateur a enregistrée et testée dans Moteurs IA (`connected`). La commande le fige comme le routage d'un run, prix du catalogue compris, puis l'ouvre par `build_engines` : la clé ne sort jamais de l'adaptateur. Un moteur non connecté arrête la commande (code 2) avant tout appel.
  - Un banc ne s'arrête jamais pour une décision humaine (`fallback = none`) : un moteur qui échoue fait échouer son cas.
  - Un moteur réel est appelé pour de vrai, et donc facturé. Il n'est utilisé que si l'utilisateur le nomme, et la commande l'annonce avant de commencer.
- **Rapport de comparaison** (`bench-<horodatage>.json/.html`). Il présente, par moteur : taux de réussite, latences p50 et p95, coût, appels, jetons d'entrée et de sortie, alertes de sécurité. Il ajoute une matrice cas × moteur et contient les rapports complets de chaque moteur. Chaque chiffre donne sa source. Un coût sans prix connu, ou des jetons qu'un appel n'annonce pas, valent `null` (« Non mesuré »). `latest.json` reste la référence de régression du moteur démo : un banc ne l'écrase pas.
- **Rédaction.** Les compteurs de jetons (`input_tokens`, `output_tokens`…) étaient masqués, parce que leur nom contient « token ». Un nombre entier sous ces noms n'est plus masqué. Toute autre valeur sous ces noms l'est toujours. Ce bug touchait aussi les traces de 5.2.

## Conséquences
- Sans moteur réel connecté, le banc ne compare que ce qui peut l'être, et il le dit. Les tests vérifient le chemin d'un moteur réel avec l'adaptateur OpenAI réel, derrière un serveur simulé (respx) : appels, jetons et coût mesurés. Aucun chiffre de fournisseur réel n'est publié tant qu'aucun n'a tourné.
- La page « Évaluations » du dashboard reste à faire. Le rapport HTML du banc en tient lieu.
- Une recette n'a pas de version : modifier une recette, c'est en enregistrer une autre. Les modèles d'équipe paramétrables (variables dans la demande) restent pour plus tard.
