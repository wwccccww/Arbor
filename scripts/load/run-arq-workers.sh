#!/usr/bin/env bash
# Run N ARQ worker processes (same env as API: DATABASE_URL, REDIS_URL, embedding keys).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

: "${DATABASE_URL:?export DATABASE_URL}"
: "${REDIS_URL:?export REDIS_URL}"

N="${WORKERS:-2}"
python3 -m pip install -e ".[api,postgres]" -q

pids=()
cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "Starting $N arbor-worker process(es) (Ctrl+C to stop all)..."
for _ in $(seq 1 "$N"); do
  arbor-worker &
  pids+=("$!")
done

while true; do
  if ! wait -n; then
    echo "A worker exited; stopping others." >&2
    exit 1
  fi
done
