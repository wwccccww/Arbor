#!/usr/bin/env bash
# Fixture stack (Scripted LLM + fixture embed + PG + Redis): queue + hybrid retrieval limits.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

: "${DATABASE_URL:?export DATABASE_URL}"
: "${REDIS_URL:?export REDIS_URL}"

PORT="${LIMIT_PORT:-8001}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
export BASE_URL
START_STACK="${START_STACK:-1}"
WORKERS="${WORKERS:-2}"

if [[ "$START_STACK" == 1 ]]; then
  if curl -sf "$BASE_URL/v1/me" -H "Authorization: Bearer token-a" -H "X-Tenant-Id: 0a000000-0000-4000-a000-000000000001" >/dev/null 2>&1; then
    echo "Using existing API at $BASE_URL"
  else
    echo "Starting fixture API on port $PORT and $WORKERS workers..."
    PORT="$PORT" ./scripts/load/serve-for-load.sh &
    api_pid=$!
    WORKERS="$WORKERS" ./scripts/load/run-arq-workers.sh &
    worker_pid=$!
    trap 'kill $api_pid $worker_pid 2>/dev/null || true' EXIT
    for _ in $(seq 1 60); do
      if curl -sf "$BASE_URL/v1/me" -H "Authorization: Bearer token-a" -H "X-Tenant-Id: 0a000000-0000-4000-a000-000000000001" >/dev/null; then
        break
      fi
      sleep 1
    done
  fi
fi

rt=$(curl -s "$BASE_URL/v1/me" -H "Authorization: Bearer token-a" -H "X-Tenant-Id: 0a000000-0000-4000-a000-000000000001")
echo "Runtime: $(python3 -c "import json,sys; print(json.loads(sys.argv[1])['runtime'])" "$rt")"
echo ""

echo "######## 1/4 Import queue throughput ########"
IMPORT_COUNT="${IMPORT_COUNT:-150}" IMPORT_PARALLEL="${IMPORT_PARALLEL:-30}" \
  IMPORT_POLL_MAX_SEC="${IMPORT_POLL_MAX_SEC:-300}" \
  ./scripts/load/import-throughput.sh
echo ""

echo "######## 2/4 Hybrid retrieval in-process ########"
python3 scripts/load/bench-hybrid-retrieval-inproc.py
echo ""

echo "######## 3/4 Hybrid retrieval HTTP (chat path) ########"
python3 scripts/load/bench-retrieval-http.py
echo ""

echo "######## 4/4 k6 stress (me + chat) ########"
BASE_URL="$BASE_URL" STRESS_SCENARIO=me STRESS_MAX_VUS="${STRESS_MAX_VUS:-400}" STRESS_STEP=50 \
  ./scripts/load/stress-find-limit.sh
BASE_URL="$BASE_URL" STRESS_SCENARIO=chat STRESS_MAX_VUS="${STRESS_CHAT_MAX_VUS:-120}" STRESS_STEP=10 \
  STRESS_P95_LIMIT_MS=15000 ./scripts/load/stress-find-limit.sh
