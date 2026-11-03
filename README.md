# NFactory

Usine logicielle IA **local-first** : décrire un besoin → plan → code → tests → livrable.
Spécification complète : [`NFACTORY_MASTER_PLAN.md`](NFACTORY_MASTER_PLAN.md) · Avancement : [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)

> **État actuel : phase 3 en cours.** Depuis « Nouveau projet », l'usine fabrique pour de vrai une **API Python**, une **application web** (React + FastAPI), un **script PowerShell**, un **classeur Excel** ou un **document Word**. Elle génère les fichiers, lance leurs tests dans un conteneur jetable sans Internet, puis livre un ZIP et le fichier final avec une explication. Une base de connaissances (documents importés, recherche avec citations) nourrit l'analyse des besoins.
> Les agents utilisent les moteurs IA configurés dans « Moteurs IA » (phase 2), ou un **modèle démo** déterministe signalé comme tel. Les types de projet pas encore construits sont affichés grisés, avec leur phase.

## Démarrer

Prérequis : Docker Desktop (démarré), `uv`, Node.js 24.

```powershell
./scripts/bootstrap.ps1   # crée .env (secrets locaux générés), lance la stack, smoke test
```

Puis ouvrir **http://127.0.0.1:3000** (dashboard) · API : http://127.0.0.1:8000/docs

Aucune clé API n'est nécessaire : le mode démo fonctionne hors ligne.

| Commande | Rôle |
|---|---|
| `./scripts/dev.ps1` | Complète les secrets manquants de `.env`, puis (re)construit et lance la stack |
| `./scripts/check.ps1` | Lint, typage et tous les tests (Python + dashboard) |
| `uv run python scripts/doctor.py` | Diagnostic : outils, services, connexions (n'affiche jamais de secret) |
| `uv run python scripts/smoke_test.py` | Vérification de bout en bout d'une stack lancée |
| `docker compose --profile telemetry up -d` | Ajoute Jaeger (traces) sur http://127.0.0.1:16686 |

Sous Linux/macOS, utiliser les équivalents `scripts/*.sh`.

## Organisation

```text
apps/api          FastAPI : routes, services, migrations Alembic, seed démo
apps/worker       Worker ARQ : pipeline LangGraph, agents, recettes, runner, fournisseurs IA
apps/sandbox      Superviseur : un conteneur jetable, sans réseau, par vérification
apps/dashboard    Next.js 16 + Tailwind + shadcn/ui + TanStack Query
apps/local-bridge Compagnon local pour Codex / Claude Code (phase 4)
packages/core-py  Modèles, machine d'états, événements, catalogue des types de projet (partagés)
scripts/          bootstrap, dev, check, doctor, smoke test
docs/             architecture et décisions (ADR)
```

Détails : [`docs/architecture.md`](docs/architecture.md).

## Conventions

- Commentaires du code en anglais ; interface et documentation produit en français.
- Tests d'abord (TDD) ; modules courts, un fichier par domaine.
- Aucune action externe (push, PR, déploiement) sans validation explicite.
