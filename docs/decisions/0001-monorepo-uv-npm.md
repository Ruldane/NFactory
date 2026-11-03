# ADR-0001 — Monorepo : workspace uv + npm

- Statut : accepté (2026-11-01)

## Contexte
Deux écosystèmes (Python pour l'API/worker, TypeScript pour le dashboard). `make` et `pnpm` ne sont pas installés sur le poste Windows de référence.

## Décision
- Python : un **workspace uv** (`packages/core-py`, `apps/api`, `apps/worker`), un seul `uv.lock`, Python 3.13 (l'hôte a 3.14, encore jeune pour l'écosystème).
- Dashboard : **npm** dans `apps/dashboard` (une seule app JS, pas besoin de workspace npm).
- Scripts `scripts/*.ps1` et `scripts/*.sh` au lieu d'un Makefile.

## Conséquences
Deux lockfiles, versions verrouillées. Aucune dépendance d'outillage supplémentaire à installer.
