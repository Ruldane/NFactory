# ADR-0003 — File de jobs : ARQ

- Statut : accepté (2026-11-01)

## Contexte
La spec demande ARQ + Redis, ou une alternative maintenue si incompatibilité. Vérification PyPI : ARQ 0.28.0 publié le 2026-04-16 (maintenu). ARQ 0.28 exige `redis<6`.

## Décision
ARQ 0.28, file `factory-runs`. `redis` (client Python) épinglé `>=5.2,<6` dans tout le workspace.

## Conséquences
Si ARQ cesse d'être maintenu ou bloque une mise à jour de `redis`, migrer vers SAQ (même modèle Redis). Le code métier ne dépend d'ARQ que dans `nfactory_worker/main.py`.
