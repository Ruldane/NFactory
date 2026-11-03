#!/usr/bin/env sh
# Start the NFactory local bridge on this machine (outside Docker), next to codex / claude / gh.
# It listens on 127.0.0.1 only. First start, or with --pair: it prints a pairing code to type
# in the dashboard (Moteurs IA, Outils locaux). Stop it with Ctrl+C.
# Repositories NFactory may work on, then exit: --allow <folder>, --revoke <id>, --repos.
# --handoff <task-id>: print how to run Claude Code yourself on a handoff, then exit.
# --allow-push <id>: allow draft PRs to the GitHub repository of that repository's origin.
set -eu
if [ "${1:-}" = "--allow" ] && [ -n "${2:-}" ]; then
  # Resolve before changing folder: a relative path means the caller's folder.
  folder=$(cd "$2" && pwd)
  shift 2
  set -- --allow "$folder" "$@"
fi
cd "$(dirname "$0")/../apps/local-bridge"
exec uv run --no-project python -m nfactory_bridge "$@"
