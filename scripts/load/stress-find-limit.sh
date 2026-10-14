#!/usr/bin/env bash
# Escalate k6 VUs until error rate or p95 exceeds thresholds (scripted API path).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export BASE_URL
SCENARIO="${STRESS_SCENARIO:-me}"  # me | chat
DURATION="${STRESS_DURATION:-20s}"
MAX_VUS="${STRESS_MAX_VUS:-200}"
STEP="${STRESS_STEP:-25}"
P95_LIMIT_MS="${STRESS_P95_LIMIT_MS:-2000}"
FAIL_RATE_LIMIT="${STRESS_FAIL_RATE:-0.05}"

script="scripts/load/k6-me.js"
if [[ "$SCENARIO" == "chat" ]]; then
  script="scripts/load/k6-chat-scripted.js"
fi

echo "Stress: $SCENARIO $BASE_URL duration=$DURATION step=$STEP max_vus=$MAX_VUS"
echo "Stop when http_req_failed > $FAIL_RATE_LIMIT or p95 > ${P95_LIMIT_MS}ms"
echo "---"

for vus in $(seq "$STEP" "$STEP" "$MAX_VUS"); do
  out=$(mktemp)
  if ! k6 run --no-thresholds "$script" --vus "$vus" --duration "$DURATION" --summary-export "$out" 2>&1 | tail -5; then
    echo "k6 run failed at VUS=$vus"
    rm -f "$out"
    break
  fi
  failed=$(python3 -c "import json; m=json.load(open('$out')); print(m['metrics']['http_req_failed']['value'])")
  p95=$(python3 -c "import json; m=json.load(open('$out')); print(m['metrics']['http_req_duration']['p(95)'])")
  rps=$(python3 -c "import json; m=json.load(open('$out')); print(round(m['metrics']['http_reqs']['rate'],1))")
  rm -f "$out"
  echo "VUS=$vus  rps=$rps  fail_rate=$failed  p95_ms=$p95"
  over_fail=$(python3 -c "print(1 if float('$failed') > float('$FAIL_RATE_LIMIT') else 0)")
  over_p95=$(python3 -c "print(1 if float('$p95') > float('$P95_LIMIT_MS') else 0)")
  if [[ "$over_fail" == 1 || "$over_p95" == 1 ]]; then
    echo ">>> Threshold exceeded at VUS=$vus (last stable step: $((vus - STEP)))"
    break
  fi
done
