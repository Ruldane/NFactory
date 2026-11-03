# Start the NFactory local bridge on this machine (outside Docker), next to codex / claude / gh.
# It listens on 127.0.0.1 only. First start, or with -Pair: it prints a pairing code to type
# in the dashboard (Moteurs IA, Outils locaux). Stop it with Ctrl+C.
# Repositories NFactory may work on, then exit: -Allow <folder>, -Revoke <id>, -Repos.
# -Handoff <task-id>: print how to run Claude Code yourself on a handoff, then exit.
# -AllowPush <id>: allow draft PRs to the GitHub repository of that repository's origin.
param([switch]$Pair, [string]$Allow, [string]$Revoke, [switch]$Repos, [string]$Handoff, [string]$AllowPush)
$ErrorActionPreference = "Continue"
$bridgeArgs = @()
if ($Allow) {
    # Resolve before changing folder: a relative path means the caller's folder.
    $resolved = Resolve-Path -LiteralPath $Allow -ErrorAction SilentlyContinue
    if (-not $resolved) { Write-Host "Dossier introuvable : $Allow"; exit 1 }
    $bridgeArgs += @("--allow", $resolved.Path)
}
if ($Revoke) { $bridgeArgs += @("--revoke", $Revoke) }
if ($Repos) { $bridgeArgs += "--repos" }
if ($Handoff) { $bridgeArgs += @("--handoff", $Handoff) }
if ($AllowPush) { $bridgeArgs += @("--allow-push", $AllowPush) }
if ($Pair) { $bridgeArgs += "--pair" }
Set-Location (Join-Path $PSScriptRoot "../apps/local-bridge")
uv run --no-project python -m nfactory_bridge @bridgeArgs
exit $LASTEXITCODE
