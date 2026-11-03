# Runs the eval scenarios (task 5.3) inside the sandbox, like a real run:
# PowerShell and Node checks included. The report lands in evals/reports/.
#   ./scripts/evals.ps1                     # every case
#   ./scripts/evals.ps1 --only powershell   # a suite or case ids
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$version = (git -C $root rev-parse --short HEAD 2>$null)
if (-not $version) { $version = "inconnue" }
docker compose --project-directory $root run --rm `
    -e "NFACTORY_VERSION=$version" `
    -v "${root}\evals:/srv/evals" `
    worker python -m nfactory_worker.evals --runner sandbox @args
exit $LASTEXITCODE
