#!/usr/bin/env bash
# API for local load tests: scripted LLM, high rate limit, no frontend build required.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

python3 -m pip install -e ".[api,postgres]" -q

# Avoid real LLM/embed latency; use in-memory demo world unless DATABASE_URL is set.
unset DEEPSEEK_API_KEY || true
unset EMBEDDING_API_KEY || true

export ARBOR_RATE_LIMIT_PER_WINDOW="${ARBOR_RATE_LIMIT_PER_WINDOW:-10000}"

echo "Load-test API: http://127.0.0.1:8000 (scripted LLM, fixture embed, rate limit=${ARBOR_RATE_LIMIT_PER_WINDOW})"
echo "Optional: DATABASE_URL + Postgres for pool/RLS path (see scripts/load/README.md)"

exec python3 -m uvicorn apps.api.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
