#!/usr/bin/env sh
# Runs the eval scenarios (task 5.3) inside the sandbox, like a real run:
# PowerShell and Node checks included. The report lands in evals/reports/.
#   ./scripts/evals.sh                      # every case
#   ./scripts/evals.sh --only powershell    # a suite or case ids
root="$(cd "$(dirname "$0")/.." && pwd)"
version="$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo inconnue)"
exec docker compose --project-directory "$root" run --rm     -e "NFACTORY_VERSION=$version"     -v "$root/evals:/srv/evals"     worker python -m nfactory_worker.evals --runner sandbox "$@"
