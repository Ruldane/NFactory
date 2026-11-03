# Référence de charge (tâche 5.6)

Mesure de base d'un seul poste, avec toute la pile en local (`./scripts/dev.ps1`) et le moteur démo. Elle sert à comparer une version à la suivante. Ce n'est pas une capacité garantie : aucun chiffre ne vaut pour un autre poste ni pour de vrais moteurs.

Pour la refaire : `uv run python scripts/load_test.py --levels 1,10,50 --duration 15 --runs 10`. Le rapport complet (JSON + Markdown) est écrit dans `loadtests/reports/`, qui n'est pas versionné.

## Mesure du 2026-11-03

- Version `e18355e-dirty` (5.2 à 5.6 pas encore commitées).
- Windows 11, 16 processeurs, Python 3.13.16. Docker Desktop fait tourner api, worker (un seul processus), Postgres, Redis et sandbox.
- Lectures : `/dashboard/summary`, `/projects?limit=20`, `/saved-recipes`, `/approvals`, appelés à tour de rôle pendant 15 s par niveau.

| Clients simultanés | Requêtes | Erreurs | Débit (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |
|---|---|---|---|---|---|---|---|
| 1 | 1145 | 0 | 76.2 | 6.9 | 34.9 | 38.4 | 139.1 |
| 10 | 1933 | 0 | 128.3 | 54.3 | 164.9 | 196.5 | 240.4 |
| 50 | 1971 | 0 | 127.7 | 284.7 | 1106.3 | 1650.0 | 2574.6 |

Runs (classeur Excel, moteur démo, vrais contrôles dans le sandbox) :

- 10 runs lancés en même temps, 10 `COMPLETED`.
- 17,7 s pour l'ensemble, soit 33,9 runs livrés par minute.
- Durée d'un run : p50 10,3 s, p95 17,7 s.

Une première mesure, faite 15 minutes plus tôt, donne les mêmes ordres de grandeur : 133,8 et 129,8 req/s, p95 à 50 clients de 1079 ms, 33,1 runs par minute.

## Lecture

- **Lectures.** Le débit plafonne vers 130 req/s dès 10 clients. Au-delà, les requêtes attendent : la latence augmente, mais aucune n'échoue. L'API tourne en un seul processus uvicorn, donc c'est le premier réglage à revoir si la charge réelle dépasse une dizaine d'utilisateurs actifs.
- **Runs.** Ils sont traités en parallèle par l'unique worker ARQ. Le temps total de 10 runs (17,7 s) est à peine plus long que le plus lent d'entre eux : la file n'est pas le goulot à ce niveau.

## Sources des chiffres

- **Latence.** Chaque requête HTTP est chronométrée côté client (`time.perf_counter`). Les percentiles sont calculés au rang le plus proche.
- **Débit.** Requêtes terminées, divisées par la durée de la phase.
- **Erreurs.** Une réponse qui n'est pas 2xx, ou aucune réponse.
- **Durée d'un run.** Du `POST` de lancement jusqu'à l'état terminal lu sur `GET /runs/{id}`. L'état est relevé toutes les 0,5 s, donc la précision est de ±0,5 s.
