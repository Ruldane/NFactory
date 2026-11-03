# NFactory — guide for AI agents

NFactory is a local-first AI software factory: a user describes a need, and a **run** turns it into a tested deliverable. Deliverables can be code (API, web app, script) or non-code (Excel workbook, Word document, report).

- **Spec**: `NFACTORY_MASTER_PLAN.md` (French). Read the section for a feature before building it.
- **Progress**: `IMPLEMENTATION_STATUS.md`. Read it before starting. Update it when you finish: task status, proof, session log.
- **Decisions**: `docs/decisions/` (ADRs). Read the relevant ADR before changing a stack choice; add an ADR when you make one.
- **Architecture**: `docs/architecture.md` lists the services, ports and test levels.

## Map

| Path | Python package / role |
|---|---|
| `packages/core-py` | `nfactory_core`: everything both API and worker use. Models (one file per domain), run state machine, events (`record_event`) and redaction, recipe catalog, pipeline steps and queue names, `Workspace`, settings. Provider adapters (`providers/`), secret store (`secrets.py`), role routing (`routing.py`), opening a stored connection (`connections.py`). |
| `apps/api` | `app`: FastAPI under `/api/v1`. HTTP lives in `routes/`, use cases in `services/`, contracts in `schemas/`. Also Alembic migrations and the demo seed. |
| `apps/worker` | `nfactory_worker`: ARQ job (`jobs/`), LangGraph pipeline (`pipeline/`), agents, recipes, runner (`LocalRunner`, `SandboxRunner`), artifacts, providers. |
| `apps/sandbox` | `nfactory_sandbox`: the sandbox supervisor (standard library). It runs each recipe check in a throwaway container of the sandbox image: no network, read-only, only that run's workspace (ADR-0005 v2). The image holds Python, pwsh + Pester + PSScriptAnalyzer, Node + `web-deps`. |
| `apps/local-bridge` | `nfactory_bridge`: the local bridge (standard library), run on the user's machine outside Docker (`scripts/bridge.ps1`). Loopback only, paired token, no shell; detects `codex` / `claude` / `gh` through their public commands, and runs Codex on a repository the user authorized (`-Allow`), in a git worktree, with consent per task, or prepares a Claude Code handoff the user runs themselves (ADR-0008). |
| `apps/dashboard` | Next.js 16 UI. It has its own `AGENTS.md`; read it before touching the frontend. |
| `scripts/` | bootstrap, dev, check, doctor, smoke test. |

## How a run works

1. The API creates a `Run` plus one `RunStep` per entry of `nfactory_core.pipeline.PIPELINE_STEPS`, then enqueues an ARQ job on the `factory-runs` queue.
2. The worker executes the steps as a LangGraph graph, checkpointed in Postgres so it resumes after a crash. `nfactory_core.roster.plan_steps(project_type)` decides which steps run (the architect only designs apps); the others are `SKIPPED` with a reason.
3. Agents return Pydantic-validated JSON. Nodes reach a model only through `call_agent`, which enforces the run's `budget`, stamps its `trace_id` and adds the call's cost. Each agent role uses the engine frozen in `runs.provider_config` at launch (`nfactory_core.routing`, ADR-0006). Temporary provider errors are retried on the same engine; any other error pauses the run for the user (`APPROVAL_PENDING`) or fails it, never switching engine silently. The requirements agent produces a `Brief`. With no routing, demo mode uses the deterministic `FakeProvider`; without demo mode, the API refuses the run (`no_model_configured`).
4. The project's **recipe** renders files into a `Workspace`.
5. A `Runner` executes the recipe's checks (lint, build, tests) with `python`, `pwsh` or `node`: `SandboxRunner` in Docker, `LocalRunner` in tests. The JUnit reports of all test checks are added up and decide pass or fail. An agent's claim never does.
6. The checks step starts with a deterministic secret scan (`nfactory_worker.security`; findings name file, line and rule, never the value). On any failure, a debug loop runs at most `MAX_REPAIR_ATTEMPTS` times; each applied patch is traced (`repair.applied`, `repair_log`, shown in the timeline). The run then ends `FAILED`; it never fakes a pass.
7. Every step emits an `Event`. Its payload is redacted and stored in `events`, where `seq` is the SSE `Last-Event-ID` the dashboard streams from. The worker then publishes on `run_channel(run_id)`, which wakes the stream (`app/wakeups.py`); the table stays the source of truth.
8. The ZIP and the deliverables (`.xlsx`, `.docx`, …) are stored as `Artifact` rows with a sha256 checksum.
9. Cancelling sets the run to `CANCELLED`; the worker checks it before each step and stops.
10. A change request on a delivered run is a child run (`parent_run_id`, scenario E). The requirements agent gets the delivered brief (`previous_brief`) and keeps the entity's table; the recipe rebuilds; checks and tests run again; the review step diffs the two workspaces (`nfactory_worker.changes`, `changes.computed`) and the package step stores `modifications.diff`.

## Adding a project type

Each project type is one recipe, and the pipeline never changes for a new one.

1. Add a `RecipeInfo` in `packages/core-py/src/nfactory_core/catalog/entries.py`. Set its `phase` to the phase that will implement it.
2. Create the package `apps/worker/nfactory_worker/recipes/<kind>/`.
   - It implements `Recipe`: `render(brief)` returns the files, the checks and the deliverable paths.
   - Templates are `*.tmpl` files with `{{placeholders}}`. The suffix keeps NFactory's own pytest and ruff away from them.
3. Register the recipe in `recipes/registry.py`.
4. Write a test that renders the recipe and runs its checks for real with `LocalRunner`.
5. The type counts as available only once `phase <= CURRENT_PHASE` and that test is green.

## Guardrails

- **Honest status.** Statuses are TODO / READY / PARTIAL / BLOCKED / DONE, and mocked features are marked DEMO. DONE requires proof (a test or command output) written into `IMPLEMENTATION_STATUS.md`. The UI shows unbuilt features as disabled, with their phase.
- **Secrets.** Never read or print `.env`, tokens or credential files. Event payloads go through `nfactory_core.events.redaction`. The runner passes children a scrubbed environment. Provider keys live only in `SecretStore` (Fernet, `secrets` table) and are read at the last moment by `open_provider`; no API response carries one. The local bridge never opens a tool's auth files: it runs public status commands and returns a status, never their output.
- **Generated content is untrusted.**
  - Every path goes through `Workspace.resolve`.
  - Commands come only from recipes, through the runner's allow-list.
  - Brief values enter generated code as Python literals (`repr`), and identifiers are regex-validated.
  - The sandbox has no network.
- **Coding agents on the user's repository.** A task needs `consent: true` from the dashboard checkbox. The bridge resolves repositories by id from its own allow-list; no request carries a path. The agent works in a `nfactory/` worktree and never commits or pushes. Its change is tested by the worker in the sandbox (`check_agent_task`), never on the bridge; NFactory never launches `claude` for the user.
- **External actions.**
  - Commit only when the user asks.
  - Push, PRs, remotes and deploys wait for explicit user approval. The code lives on the public `Ruldane/NFactory` (`origin`); NFactory's own draft-PR tests target only the private `Ruldane/nfactory-test`.
  - No auto-merge.
  - No silent fallback to an external LLM provider.
- **Docker.** `docker.sock` is mounted only into `sandbox-supervisor`, never into `api` or `worker`. The supervisor builds every container spec itself; nothing in a request sets a container option. All ports bind to `127.0.0.1`. The supervisor publishes no port and gets only `NFACTORY_SANDBOX_TOKEN` from `.env`. A preview of a generated app (`RenderedProject.preview`) runs on the internal `nfactory_preview` network with its workspace read-only; `preview-gateway` (no socket, no secret, port 8090, another origin than the dashboard) is its only way in.

## Conventions

- **Test first**: write the failing test, watch it go red, then make it green.
- **Small modules**: one domain per file, a small interface stated in the package `__init__.py`, dependencies passed in rather than created.
- **Language**: comments and docstrings in English. User-facing text in French: UI and API error `message`. API error `code` values stay stable English slugs.
- **API errors** use the shape `{"error": {"code", "message", "details"}}`, built through `app.errors`.
- **Workspace scope**: every query is scoped through `RequestContext`. An ID from another workspace returns 404, exactly like a missing one.

## Commands

| Goal | Command |
|---|---|
| Install / sync | `uv sync --all-packages` (plain `uv sync` drops workspace members' dependencies) |
| Full gate (must be green before "done") | `./scripts/check.ps1` or `./scripts/check.sh` |
| Test services | `docker compose up -d --wait postgres redis` |
| One test folder | `uv run pytest apps/worker/tests/runner -q` |
| Dashboard | `npm --prefix apps/dashboard test`, `run lint`, `run typecheck` |
| Whole stack + smoke | `./scripts/dev.ps1` (fills missing `.env` secrets, then `docker compose up -d --build`), then `uv run python scripts/smoke_test.py` |

## Gotchas

- `respx.mock(...)` with arguments builds a separate router: routes added with module-level `respx.get(...)` are then not active. Use bare `@respx.mock`.
- The ARQ worker keeps no job result (`keep_result: 0`): the job id is the run id, and a kept result would silently drop the re-enqueue of a paused run.
- New event types go in both `nfactory_core/events/contract.py` and `apps/dashboard/lib/run-events.ts`; a test checks the two lists match.
- Alembic autogenerate ignores LangGraph's checkpoint tables (`include_name` in `migrations/env.py`); still review every generated migration.
- A recipe whose checks need `pwsh` or `node` runs them in the sandbox image. Its tests use the local tools when present, else `nfactory-sandbox:latest` (`docker compose build sandbox-supervisor`), else they skip and say why.
- The sandbox has no Internet, so generated frontends link the preinstalled toolchain (`apps/sandbox/web-deps`), one link per package in a real `node_modules` (Vite writes there). A recipe pins exactly those versions; a test checks it.
- Generated `.ps1` files need a UTF-8 BOM (PSScriptAnalyzer). In Pester, `TestDrive` is shared by a whole `Describe`: give each test its own file names.
- `Workspace.files()` never follows a link (symlink or Windows junction) and skips `node_modules`: generated code may plant a link pointing outside the workspace.

- Use `127.0.0.1`, never `localhost`: IPv6 resolution stalls about 2 minutes on Windows. Host ports are Postgres 55432 and Redis 56379.
- On Windows, async psycopg needs the selector event loop, set in the root `conftest.py` and `app.bootstrap`. That loop cannot spawn asyncio subprocesses, so the runner calls `subprocess.run` in a thread.
- pytest uses `--import-mode=importlib`, and test folders have no `__init__.py`. So `from conftest import …` is unreliable: share helpers through fixtures. The PostgreSQL fixtures (`migrated_database_url`, `db_session`) live in the root `conftest.py`.
- ARQ 0.28 requires `redis<6`; that pin is deliberate. ARQ locks a running job for its whole timeout: a killed worker's run is released by `jobs/recovery.py` (Redis lease), not by ARQ.
- The SQLAlchemy URL is `postgresql+psycopg://`. LangGraph's checkpointer wants the plain `postgresql://` form.
- `.ps1` scripts target Windows PowerShell 5.1: UTF-8 with BOM, `$ErrorActionPreference = "Continue"`, and failures detected through `$LASTEXITCODE`.
- Under Cache Components (Next 16), runtime data such as route `params` and `usePathname()` must be read inside `<Suspense>`, and `crypto.randomUUID()` belongs in event handlers, or `next build` fails while prerendering.
