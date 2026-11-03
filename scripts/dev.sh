#!/usr/bin/env sh
# Start (or rebuild) the full local stack, then open http://127.0.0.1:3000
set -eu
cd "$(dirname "$0")/.."
# The sandbox token may be missing from an older .env.
python3 scripts/ensure_secrets.py
docker compose up -d --build
echo "Dashboard : http://127.0.0.1:3000   API : http://127.0.0.1:8000/docs"
