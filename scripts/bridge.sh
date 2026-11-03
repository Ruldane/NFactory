#!/usr/bin/env sh
# Start the NFactory local bridge on this machine (outside Docker), next to codex / claude / gh.
# It listens on 127.0.0.1 only. First start, or with --pair: it prints a pairing code to type
# in the dashboard (Moteurs IA, Outils locaux). Stop it with Ctrl+C.
set -eu
cd "$(dirname "$0")/../apps/local-bridge"
exec uv run --no-project python -m nfactory_bridge "$@"
