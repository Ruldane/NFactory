# Start (or rebuild) the full local stack, then open http://127.0.0.1:3000
# Native tools (docker, npm) write progress to stderr; PowerShell 5.1 would treat that
# as fatal under "Stop". Failures are detected through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
# The sandbox token may be missing from an older .env.
uv run python scripts/ensure_secrets.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Dashboard : http://127.0.0.1:3000   API : http://127.0.0.1:8000/docs"
