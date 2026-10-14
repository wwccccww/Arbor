#!/usr/bin/env bash
# API for integration / smoke load: real DeepSeek + bge-m3 (or EMBEDDING_*), Postgres, Redis queue.
# Pair with one or more `arbor-worker` processes (see run-arq-workers.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

: "${DATABASE_URL:?export DATABASE_URL (API and workers must share the same DB)}"
: "${REDIS_URL:?export REDIS_URL for async import jobs}"
: "${DEEPSEEK_API_KEY:?export DEEPSEEK_API_KEY}"

if [[ -z "${EMBEDDING_API_KEY:-}" && -z "${SILICONFLOW_API_KEY:-}" ]]; then
  echo "Set EMBEDDING_API_KEY or SILICONFLOW_API_KEY for bge-m3 (or your EMBEDDING_MODEL)." >&2
  exit 1
fi

python3 -m pip install -e ".[api,postgres]" -q

export ARBOR_RATE_LIMIT_PER_WINDOW="${ARBOR_RATE_LIMIT_PER_WINDOW:-10000}"
export EMBEDDING_MODEL="${EMBEDDING_MODEL:-BAAI/bge-m3}"

echo "Load-test API (real LLM + embed): http://127.0.0.1:8000"
echo "  DATABASE_URL=set  REDIS_URL=${REDIS_URL}"
echo "  DEEPSEEK_CHAT_MODEL=${DEEPSEEK_CHAT_MODEL:-deepseek-chat}"
echo "  EMBEDDING_MODEL=${EMBEDDING_MODEL}"
echo "  rate limit/window=${ARBOR_RATE_LIMIT_PER_WINDOW}"
echo "Start workers: ./scripts/load/run-arq-workers.sh   # default 2 processes"
echo "Verify: curl -s -H 'Authorization: Bearer token-a' -H 'X-Tenant-Id: 0a000000-0000-4000-a000-000000000001' http://127.0.0.1:8000/v1/me | python3 -m json.tool"

exec python3 -m uvicorn apps.api.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
