# ADR-0009 — Traces des runs : OpenTelemetry, avec la base pour la vue du dashboard

- Statut : accepté (2026-11-03)

## Contexte
La tâche 5.2 (spec §14.1, Live Factory §616) demande des traces, la durée, le coût et les tentatives par étape. Le worker enregistre déjà, pour chaque run, les étapes (`run_steps`) et des événements mesurés : `agent.progress` (fournisseur, modèle, jetons, durée, coût) et `tool.invoked` (vérification, code de sortie, durée). Chaque run a un `trace_id` de 32 caractères hexadécimaux. La spec cite OpenTelemetry pour l'observabilité, et React Flow « si utile » pour le graphe.

## Décision
- **Des spans OpenTelemetry, tirés des événements existants.** `nfactory_worker.telemetry.TracingReporter` enveloppe le reporter du pipeline. Il transmet chaque appel tel quel et en tire des spans : `run` → `step <nom>` → `agent <rôle>` / `check <nom>`. Le pipeline ne change pas.
  - Les spans utilisent le `trace_id` du run (`nfactory_core.telemetry.run_context`). La trace dans Jaeger et le run dans le dashboard portent le même identifiant.
  - Un appel d'agent ou une vérification produit un événement à la fin. Son span finit à ce moment-là et commence `duration_s` plus tôt.
  - Attributs : uniquement des mesures, nommées selon les conventions GenAI (`gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`…) et `nfactory.*` (étape, état, coût, résultat). Jamais de prompt, de sortie, ni le texte d'une commande. Une vérification qui échoue, une étape en échec et un run `FAILED` ont le statut `ERROR`.
- **Export seulement si un collecteur est configuré.** Sans `OTEL_EXPORTER_OTLP_ENDPOINT`, aucun traceur n'est créé et rien ne sort. Compose transmet `NFACTORY_OTLP_ENDPOINT` (vide par défaut). Le profil `telemetry` ajoute Jaeger : son interface est publiée sur `127.0.0.1:16686`, et le port OTLP reste sur le réseau interne.
- **Le dashboard ne dépend pas du collecteur.** `GET /runs/{id}/trace` reconstruit le même arbre depuis la base : étapes enregistrées, puis appels et vérifications sous leur étape, avec durée, jetons et coût. Le coût d'une étape est la somme de ses appels, ou `null` dès qu'un appel n'a pas de prix connu. Un 0 inventé n'apparaît jamais. Une valeur expurgée lue dans un ancien événement donne `null`.
- **Pas de React Flow.** La chaîne d'agents est linéaire, avec une seule boucle de correction. Le graphe HTML existant (`AgentGraph`, une liste ordonnée) l'affiche déjà, reste accessible au lecteur d'écran et n'ajoute aucune dépendance. Il affiche désormais aussi le nombre d'appels et le coût de chaque étape. La cascade « Trace du run » montre l'axe du temps.

## Conséquences
- Une étape qui reprend après un redémarrage du worker n'a pas de span de début dans le nouveau processus. Le traceur ignore sa fin. La vue de l'API, qui lit la base, reste complète.
- Le temps d'un span d'appel vient de l'horloge du worker, et celui de la vue API de `events.created_at`. Les deux sont proches, sans être garantis identiques à la milliseconde.
- L'API n'émet pas encore ses propres spans (requêtes HTTP). Si on le fait plus tard, on réutilisera `tracer_provider`.
