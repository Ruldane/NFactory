# First-time setup: creates .env with fresh local secrets (never printed), then starts the stack.
# Native tools (docker, npm) write progress to stderr; PowerShell 5.1 would treat that
# as fatal under "Stop". Failures are detected through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")

# Creates .env if needed and fills missing generated secrets (names printed, values never).
uv run python scripts/ensure_secrets.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/smoke_test.py
exit $LASTEXITCODE
