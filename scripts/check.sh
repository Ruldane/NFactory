#!/usr/bin/env sh
# Full quality gate: lint, types, unit + integration tests (Python and dashboard).
set -eu
cd "$(dirname "$0")/.."
docker compose up -d --wait postgres redis
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/core-py/src apps/api/app apps/worker/nfactory_worker apps/local-bridge/nfactory_bridge
uv run pytest
npm --prefix apps/dashboard run lint
npm --prefix apps/dashboard run typecheck
npm --prefix apps/dashboard test
echo "Toutes les vérifications passent."
