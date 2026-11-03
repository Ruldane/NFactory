# Full quality gate: lint, types, unit + integration tests (Python and dashboard).
# Starts PostgreSQL and Redis if needed. Exits non-zero on the first failure.
# Native tools (docker, npm) write progress to stderr; PowerShell 5.1 would treat that
# as fatal under "Stop". Failures are detected through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")

function Step([string]$name, [scriptblock]$command) {
    Write-Host "`n== $name" -ForegroundColor Cyan
    & $command
    if ($LASTEXITCODE -ne 0) { Write-Host "ECHEC : $name" -ForegroundColor Red; exit $LASTEXITCODE }
}

Step "Services de test (PostgreSQL, Redis)" { docker compose up -d --wait postgres redis }
Step "Ruff (lint)" { uv run ruff check . }
Step "Ruff (format)" { uv run ruff format --check . }
Step "Mypy" { uv run mypy packages/core-py/src apps/api/app apps/worker/nfactory_worker apps/local-bridge/nfactory_bridge }
Step "Pytest" { uv run pytest }
Step "Dashboard : ESLint" { npm --prefix apps/dashboard run lint }
Step "Dashboard : TypeScript" { npm --prefix apps/dashboard run typecheck }
Step "Dashboard : Vitest" { npm --prefix apps/dashboard test }
Write-Host "`nToutes les vérifications passent." -ForegroundColor Green
