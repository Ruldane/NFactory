# Start the NFactory local bridge on this machine (outside Docker), next to codex / claude / gh.
# It listens on 127.0.0.1 only. First start, or with -Pair: it prints a pairing code to type
# in the dashboard (Moteurs IA, Outils locaux). Stop it with Ctrl+C.
param([switch]$Pair)
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "../apps/local-bridge")
$bridgeArgs = @()
if ($Pair) { $bridgeArgs += "--pair" }
uv run --no-project python -m nfactory_bridge @bridgeArgs
exit $LASTEXITCODE
