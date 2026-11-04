# Architecture (état phase 3, en cours)

Référence cible : `NFACTORY_MASTER_PLAN.md` §4. Ce document décrit ce qui **existe**.

## Services (Docker Compose)

| Service | Image / code | Rôle | Port hôte |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:0.8.7-pg18` | Données durables, pgvector, checkpoints LangGraph | 127.0.0.1:55432 |
| `redis` | `redis:7.4-alpine` | File de jobs, pub/sub | 127.0.0.1:56379 |
| `migrate` | `apps/api` | One-shot : migrations, identité locale, seed démo | — |
| `api` | `apps/api` | FastAPI `/api/v1` ; lit les workspaces en lecture seule | 127.0.0.1:8000 |
| `worker` | `apps/worker` | Worker ARQ, file `factory-runs`, graphe LangGraph | — |
| `sandbox-supervisor` | `apps/sandbox` (image `nfactory-sandbox`) | Lance un conteneur jetable et confiné par vérification de recette (ADR-0005 v2) | — (réseau interne) |
| `preview-gateway` | image `nfactory-sandbox` | Seule entrée vers l'aperçu d'une app générée (`/preview/<run>/`), autre origine que le dashboard ; ni socket Docker ni secret | 127.0.0.1:8090 |
| `dashboard` | `apps/dashboard` | Next.js, proxy `/api/v1` → `api` | 127.0.0.1:3000 |
| `jaeger` | profil `telemetry` | Traces (optionnel) | 127.0.0.1:16686 |

Hors Docker : le **pont local** (`apps/local-bridge`, `scripts/bridge.ps1`) tourne sur l'ordinateur de l'utilisateur, à côté de `codex`, `claude` et `gh`, sur `127.0.0.1:8765` uniquement. L'API le joint par `host.docker.internal` (ADR-0008).

Tous les ports sont liés à `127.0.0.1` uniquement. Les conteneurs applicatifs tournent avec un utilisateur non-root (uid 10001 / `node`). Seul `sandbox-supervisor` monte `docker.sock` ; jamais `api` ni `worker`.

Réseaux : `default` pour les services applicatifs ; `sandbox` (`internal: true`, sans accès extérieur) relie `worker`, `api` (démarrer et arrêter un aperçu) et `sandbox-supervisor` ; `preview` (`nfactory_preview`, `internal: true`) relie seulement les conteneurs d'aperçu et `preview-gateway` ; `gateway` sert uniquement à publier le port de la passerelle. Le superviseur ne reçoit de `.env` que `NFACTORY_SANDBOX_TOKEN`. Les conteneurs de vérification n'ont aucun réseau (`none`).

Volumes : `artifacts` (worker en écriture, api en lecture), `workspaces`, nommé `nfactory_workspaces` (worker en écriture ; api et superviseur en lecture seule ; chaque conteneur de vérification ne monte que le sous-dossier de son run).

## Déroulé d'un run

```text
dashboard ─POST /projects/{id}/runs─▶ api ─Run QUEUED + 9 RunStep─▶ Postgres
                                       └─enqueue run_factory(run_id)─▶ Redis
worker ◀─job─ Redis
  claim (RUNNING) ─▶ graphe LangGraph (checkpoint Postgres par étape)
    requirements → plan → architect → build → checks → tests → review → docs → package
                                   ▲            │
                                   └── debug ◀──┘ (échec : au plus MAX_REPAIR_ATTEMPTS)
    checks/tests ─HTTP + jeton─▶ sandbox-supervisor ─▶ 1 conteneur jetable par commande
                                 (ruff, pwsh/Pester, node/Vite/Vitest, pytest → JUnit)
  chaque étape : RunStep + Event (payload masqué) ; fin : Artifact (ZIP + livrables, sha256)
dashboard ◀─SSE /runs/{id}/events (Last-Event-ID = seq)─ api ◀─ table events
                                          api ◀─ Redis nfactory:run:{id} (réveil) ◀─ worker
```

Le flux SSE relit la table dès que le worker signale un événement sur Redis, et la relit de toute façon toutes les 2 s ; sans Redis, il la relit toutes les 0,5 s. Chaque run reçoit au lancement un `trace_id` et un budget (`max_llm_calls`, `max_agent_steps`, `max_repair_attempts`) que le worker applique.

Traces (tâche 5.2, ADR-0009) : `GET /runs/{id}/trace` reconstruit depuis la base l'arbre run → étapes → appels d'agent et vérifications, avec durée, jetons et coût ; le dashboard l'affiche en cascade (« Trace du run »). Si `NFACTORY_OTLP_ENDPOINT` est fixé, le worker exporte aussi ces spans en OTLP/HTTP sous le `trace_id` du run, par exemple vers Jaeger (`docker compose --profile telemetry up`, interface sur `127.0.0.1:16686`).

Connexion (tâche 6.1, ADR-0013) : en mode `local` (défaut), un seul utilisateur, sans connexion. En mode `oidc`, le dashboard envoie le navigateur chez Google (`/auth/login`, flux Authorization Code + PKCE conduit par l'API) ; au retour (`/auth/callback`, par le dashboard), l'API vérifie le jeton d'identité, applique la règle d'admission (domaine Workspace `hd` ou e-mail listé, refus par défaut) et pose un cookie de session `HttpOnly`, `SameSite=Lax`, dont seule l'empreinte est en base (`auth_sessions`). Toute route sauf `/health*` et `/auth/*` exige alors une session ; une modification doit venir de l'origine du dashboard.

Droits et audit (tâche 5.4, ADR-0011) : chaque route qui modifie quelque chose déclare sa permission (`CanBuild`, `CanApprove`, `CanConfigure`, `CanAudit`), tirée du rôle de l'appelant dans l'espace de travail ; un rôle insuffisant reçoit 403 `forbidden`. Les actions sensibles (annulation, décisions, réglages, moteurs, routage, appairage, publication) écrivent une entrée expurgée dans `audit_log`, rattachée à l'espace. `GET /me`, `GET /approvals` et `GET /audit` alimentent la page « Approbations & audit » du dashboard.

Marquage IA (AI Act art. 50, ADR-0014) : l'étape `package` écrit `.nfactory/provenance.json` (généré par IA, terme IPTC `trainedAlgorithmicMedia`, moteur de chaque rôle, sha256 de chaque fichier, sans horodatage) et le livre dans le ZIP ; les `.xlsx` et `.docx` le disent dans leurs propriétés, les README et `EXPLICATION.md` en toutes lettres ; le dashboard le rappelle au lancement et au-dessus des livrables.

Recettes (tâche 5.5, ADR-0012) : un run livré s'enregistre comme recette de l'espace de travail (`/saved-recipes`) ; la relancer crée un nouveau projet et lance un run par le chemin habituel (`launch_run`), avec les moteurs et les limites du moment.

Pendant un run, le worker tient un bail Redis (`nfactory:run-lease:<id>`, 30 s, renouvelé). Au démarrage du worker et chaque minute, un run `RUNNING` sans bail vivant est libéré du verrou ARQ et reprend à son dernier checkpoint : un worker tué ne bloque pas son run pendant le délai maximal du job.

Les limites d'un run (`max_llm_calls`, `max_agent_steps`, `max_repair_attempts`) viennent des réglages de l'espace de travail (`GET/PUT /settings`, stockés dans `workspaces.data_policy`), à défaut des variables d'environnement.

Le verdict des tests vient du rapport JUnit, jamais d'un agent. L'annulation passe le run à `CANCELLED` ; le worker s'arrête avant l'étape suivante.

## Moteurs IA (phase 2, ADR-0006)

```text
dashboard /providers ─PUT /providers/{kind}/configuration─▶ api ─clé chiffrée (Fernet)─▶ table secrets
                     ─POST /providers/{kind}/validate─▶ api ─httpx─▶ fournisseur (test consenti)
                     ─PUT /routing─▶ api ─▶ workspaces.data_policy["routing"]
lancement : routage figé dans runs.provider_config (un moteur par rôle, avec son prix)
worker : build_engines ─clé lue au dernier moment─▶ un LLM par rôle ─▶ call_agent
  erreur passagère → réessai sur le même moteur ; autre erreur →
    fallback "ask_user" : APPROVAL_PENDING + Approval provider_fallback → POST /runs/{id}/approvals/{id}/approve|reject
    fallback "none" : FAILED avec le motif du fournisseur
```

Les adaptateurs (`nfactory_core.providers`) sont partagés par l'API et le worker. Sans routage, le mode démo s'applique s'il est actif ; sinon l'API refuse le run (`409 no_model_configured`). Une route vers un fournisseur non testé (`provider_not_ready`) ou distant en mode local uniquement (`local_only_violation`) est refusée au lancement. Le coût d'un run est la somme des appels au prix saisi dans le catalogue, ou « Non mesuré » si un seul prix manque.

## Outils locaux (phase 4, ADR-0008)

```text
utilisateur : scripts/bridge.ps1 ─▶ pont 127.0.0.1:8765 (affiche un code d'appairage)
dashboard /providers ─POST /local-runtimes/pairing {code}─▶ api ─host.docker.internal─▶ pont /pair
  jeton ─▶ SecretStore (connexion local_bridge), jamais renvoyé ; le pont ne garde que son SHA-256
dashboard ─GET /local-runtimes─▶ api ─Bearer─▶ pont /runtimes ─▶ codex/claude/gh --version + statut officiel
utilisateur : bridge.ps1 -Allow <dossier> ─▶ repos.json (le navigateur ne voit que des noms)
dashboard /agents ─POST /local-runtimes/tasks {repo_id, task, consent: true}─▶ api ─▶ pont /tasks
  pont : git worktree + branche nfactory/<dépôt>/<tâche> ─▶ codex exec --json (sans réseau)
  dashboard ─GET /local-runtimes/tasks/{id} toutes les 2 s─▶ événements réduits, manifeste, diff
relais Claude : pont = worktree + brief ; l'utilisateur lance claude (bridge.ps1 -Handoff) ; POST …/collect
test : POST /local-runtimes/tasks/{id}/checks ─▶ agent_checks + job check_agent_task
  worker ─GET pont /tasks/{id}/snapshot─▶ Workspace jetable ─▶ superviseur sandbox (pytest) ─▶ JUnit ─▶ verdict
utilisateur : bridge.ps1 -AllowPush <id> ─▶ repos.json garde owner/nom du remote origin (seule cible)
publication : POST /local-runtimes/tasks/{id}/publish {approve: true, title} ─▶ audit_log ─▶ pont /publish
  pont : commit local ─▶ git push de la branche nfactory/… seule ─▶ gh pr create --draft
  GET …/publication ─▶ pont relit commit, branche et PR sur GitHub (gh api, gh pr list)
```

Le pont refuse les navigateurs (`Origin`), les hôtes inconnus (rebinding DNS) et toute requête sans jeton, sauf `/health`. Aucune route n'exécute une commande issue de la requête.

## Code Python

- `packages/core-py` (`nfactory_core`) : configuration, modèles SQLAlchemy, machine d'états, contrat d'événements (+ `record_event`), catalogue de recettes, étapes du pipeline, `Workspace` (chemins confinés), `providers/` (adaptateurs, erreurs, SSRF, prix), `secrets.py`, `routing.py`, `connections.py`.
- `apps/api` (`app`) : `main.create_app(settings, queue)`, `routes/` (HTTP fin), `services/` (cas d'usage filtrés par workspace), `schemas/`, `queue.py` (ARQ ou mémoire), `demo/`, `bootstrap.py`.
- `apps/worker` (`nfactory_worker`) : `main.py` (réglages ARQ, job `run_factory`), `jobs/` (cycle de vie et adaptateurs base), `pipeline/` (graphe, nœuds, ports), `agents/` (un fichier par agent + cerveau démo), `recipes/` (un paquet par type), `runner/` (`LocalRunner`, `SandboxRunner`, JUnit), `artifacts/`, `providers/`.
- `apps/sandbox` : `nfactory_sandbox` (superviseur : `server.py` HTTP, `containers.py` spécification et cycle de vie des conteneurs, `engine.py` client Docker), `Dockerfile` de l'image (Python, pwsh + Pester + PSScriptAnalyzer, Node + `web-deps`). Bibliothèque standard seulement.

## Identité et isolation

Mode local : un utilisateur `usr_local` propriétaire de l'espace `wks_local`. Toutes les requêtes passent par un `RequestContext`. Un projet, un run ou un artefact hors de ces workspaces renvoie `404`, comme un objet inexistant.

## Erreurs

Format unique : `{"error": {"code", "message", "details"}}`. `code` est stable et en anglais, `message` est en français.

## Tests

| Niveau | Où | Base réelle ? |
|---|---|---|
| Unitaires Python | `packages/core-py/tests`, `apps/worker/tests`, `apps/sandbox/tests`, `apps/local-bridge/tests`, `scripts/tests` | non |
| Recettes | `apps/worker/tests/recipes` : chaque projet généré lance ses vrais ruff/pytest | non |
| Intégration | `apps/api/tests`, `apps/worker/tests/jobs`, `apps/worker/tests/pipeline/test_resume.py` (base jetable par test) | oui |
| Dashboard | `apps/dashboard/**/*.test.ts(x)` (Vitest + Testing Library) | non (fetch simulé) |
| Bout en bout | `scripts/smoke_test.py` sur la stack lancée (dont un vrai run Excel) | oui |
| E2E navigateur (tâche 5.6) | `apps/dashboard/e2e/*.e2e.ts` (Playwright, Chromium) sur la stack lancée en mode démo : besoin → run → classeur téléchargé, recette enregistrée puis relancée, limites auditées, centre d'approbation | oui |
| Charge de base (tâche 5.6) | `scripts/load_test.py` : lectures concurrentes et runs démo simultanés ; refuse si un moteur réel est routé ; référence dans `docs/load-baseline.md` | oui (moteur démo) |
| Évals (ADR-0010) | `evals/datasets/*.toml` (37 scénarios), `scripts/evals.ps1` dans le sandbox ou `uv run python -m nfactory_worker.evals` en local ; rapport JSON/HTML dans `evals/reports/` | non (pipeline réel, moteur démo) |
| Comparaison des moteurs (ADR-0012) | mêmes cas avec `--engine demo --engine <fournisseur>:<modèle>` ; un moteur réel doit être connecté dans Moteurs IA ; rapport `bench-*.json/.html` | oui, si un moteur réel est nommé (facturé) |
