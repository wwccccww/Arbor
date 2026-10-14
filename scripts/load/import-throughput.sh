#!/usr/bin/env bash
# Measure import queue enqueue rate and worker drain throughput (jobs completed / window).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TENANT="${TENANT_ID:-0a000000-0000-4000-a000-000000000001}"
PERSONA="${PERSONA_ID:-0a000000-0000-4000-a000-000000000010}"
TOKEN="${DEMO_TOKEN:-token-a}"
N="${IMPORT_COUNT:-120}"
PARALLEL="${IMPORT_PARALLEL:-20}"
SAMPLE_SEC="${THROUGHPUT_SAMPLE_SEC:-5}"
POLL_MAX="${IMPORT_POLL_MAX_SEC:-600}"
DRAIN="${IMPORT_DRAIN:-1}"

TMPDIR="$(mktemp -d)"
JOBS_FILE="$TMPDIR/job_ids.txt"
trap 'rm -rf "$TMPDIR"' EXIT

submit_one() {
  local i="$1"
  local f="$TMPDIR/import-$i.txt"
  printf '导入压测片段 #%s\n租户A林夏相关事实：2024年测试条目 %s。\n' "$i" "$i" > "$f"
  local resp code body jid
  resp=$(curl -sS -w "\n%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-Tenant-Id: $TENANT" \
    -F "file=@${f};filename=backlog-${i}.txt" \
    -F "hint=load-test" \
    "$BASE_URL/v1/personas/${PERSONA}/imports")
  code=$(echo "$resp" | tail -n1)
  body=$(echo "$resp" | sed '$d')
  if [[ "$code" != "202" ]]; then
    echo "FAIL submit $i: HTTP $code $body" >&2
    return 1
  fi
  jid=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['job_id'])" "$body")
  echo "$jid"
}

export -f submit_one
export TMPDIR TENANT TOKEN PERSONA BASE_URL

echo "=== Import queue throughput ==="
echo "target=$BASE_URL count=$N parallel=$PARALLEL sample=${SAMPLE_SEC}s poll_max=${POLL_MAX}s"
started=$(date +%s)

if [[ "$PARALLEL" -le 1 ]]; then
  : >"$JOBS_FILE"
  for i in $(seq 1 "$N"); do
    submit_one "$i" >>"$JOBS_FILE"
  done
else
  seq 1 "$N" | xargs -P "$PARALLEL" -I {} bash -c 'submit_one "$@"' _ {} >>"$JOBS_FILE"
fi

submit_done=$(date +%s)
submit_sec=$((submit_done - started))
mapfile -t job_ids <"$JOBS_FILE"
job_count=${#job_ids[@]}
submit_rps=$(python3 -c "print(round($job_count/max($submit_sec,1),2))")
echo "Enqueued $job_count jobs in ${submit_sec}s (~${submit_rps} submit/s)"

count_status() {
  local st="$1"
  python3 <<PY
import json, subprocess, sys
jobs = open("$JOBS_FILE").read().splitlines()
token, tenant, base = "$TOKEN", "$TENANT", "$BASE_URL"
st = "$st"
n = 0
for jid in jobs:
    out = subprocess.check_output([
        "curl", "-sS",
        "-H", f"Authorization: Bearer {token}",
        "-H", f"X-Tenant-Id: {tenant}",
        f"{base}/v1/imports/{jid}",
    ])
    if json.loads(out).get("status") == st:
        n += 1
print(n)
PY
}

max_pending=0
max_running=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  p=$(count_status pending)
  r=$(count_status running)
  max_pending=$((p > max_pending ? p : max_pending))
  max_running=$((r > max_running ? r : max_running))
  sleep 0.1
done
echo "Peak pending≈$max_pending  peak running≈$max_running"

prev_completed=$(count_status completed)
prev_ts=$submit_done
deadline=$((submit_done + POLL_MAX))
echo "--- throughput samples (completed delta / ${SAMPLE_SEC}s) ---"
while [[ $(date +%s) -lt $deadline ]]; do
  sleep "$SAMPLE_SEC"
  now=$(date +%s)
  pending=$(count_status pending)
  running=$(count_status running)
  completed=$(count_status completed)
  failed=$(count_status failed)
  delta=$((completed - prev_completed))
  window=$((now - prev_ts))
  jps=$(python3 -c "print(round($delta/max($window,1),3))")
  echo "$(date +%H:%M:%S)  pending=$pending running=$running completed=$completed failed=$failed  Δcompleted=$delta  ~${jps} jobs/s"
  prev_completed=$completed
  prev_ts=$now
  if [[ "$DRAIN" == 1 && "$pending" == 0 && "$running" == 0 ]]; then
    break
  fi
done

finished=$(date +%s)
completed=$(count_status completed)
failed=$(count_status failed)
pending=$(count_status pending)
running=$(count_status running)
wall=$((finished - started))
avg_jps=$(python3 -c "print(round($completed/max($wall,1),3))")
echo "---"
echo "Wall ${wall}s | completed=$completed failed=$failed pending=$pending running=$running"
echo "Avg completed/wall ≈ ${avg_jps} jobs/s (end-to-end incl. submit)"
[[ "$failed" == 0 ]] || exit 1
if [[ "$DRAIN" == 1 ]]; then
  [[ "$pending" == 0 && "$running" == 0 ]] || exit 1
fi
