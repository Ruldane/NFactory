#!/usr/bin/env sh
# First-time setup: creates .env with fresh local secrets (never printed), then starts the stack.
set -eu
cd "$(dirname "$0")/.."

# Creates .env if needed and fills missing generated secrets (names printed, values never).
python3 scripts/ensure_secrets.py

docker compose up -d --build
python3 scripts/smoke_test.py
