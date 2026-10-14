#!/usr/bin/env bash
# Submit N import jobs quickly and poll until queue drains (async Redis + worker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TENANT="${TENANT_ID:-0a000000-0000-4000-a000-000000000001}"
PERSONA="${PERSONA_ID:-0a000000-0000-4000-a000-000000000010}"
TOKEN="${DEMO_TOKEN:-token-a}"
N="${IMPORT_COUNT:-25}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "Submitting $N import jobs to $BASE_URL (persona=$PERSONA)"
job_ids=()
started=$(date +%s)

for i in $(seq 1 "$N"); do
  f="$TMPDIR/import-$i.txt"
  printf '导入压测片段 #%s\n租户A林夏相关事实：2024年测试条目 %s。\n' "$i" "$i" > "$f"
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
    exit 1
  fi
  jid=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['job_id'])" "$body")
  job_ids+=("$jid")
done

submit_done=$(date +%s)
echo "All submitted in $((submit_done - started))s. First status snapshot:"

count_status() {
  local st="$1"
  local n=0
  for jid in "${job_ids[@]}"; do
    s=$(curl -sS -H "Authorization: Bearer $TOKEN" -H "X-Tenant-Id: $TENANT" \
      "$BASE_URL/v1/imports/${jid}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")
    if [[ "$s" == "$st" ]]; then
      n=$((n + 1))
    fi
  done
  echo "$n"
}

pending=$(count_status pending)
running=$(count_status running)
completed=$(count_status completed)
failed=$(count_status failed)
echo "  pending=$pending running=$running completed=$completed failed=$failed"

echo "Polling every 2s until no pending/running (max 120s)..."
deadline=$(( $(date +%s) + 120 ))
while [[ $(date +%s) -lt $deadline ]]; do
  pending=$(count_status pending)
  running=$(count_status running)
  completed=$(count_status completed)
  failed=$(count_status failed)
  echo "  $(date +%H:%M:%S) pending=$pending running=$running completed=$completed failed=$failed"
  if [[ "$pending" == 0 && "$running" == 0 ]]; then
    break
  fi
  sleep 2
done

pending=$(count_status pending)
running=$(count_status running)
completed=$(count_status completed)
failed=$(count_status failed)
finished=$(date +%s)
echo "---"
echo "Total wall time: $((finished - started))s"
echo "Final: pending=$pending running=$running completed=$completed failed=$failed"
if [[ "$failed" != 0 ]]; then
  echo "Sample failed job:"
  for jid in "${job_ids[@]}"; do
    curl -sS -H "Authorization: Bearer $TOKEN" -H "X-Tenant-Id: $TENANT" \
      "$BASE_URL/v1/imports/${jid}" | python3 -c "import json,sys; j=json.load(sys.stdin); print(j) if j.get('status')=='failed' else None" 2>/dev/null | head -1 && break
  done
fi
[[ "$pending" == 0 && "$running" == 0 && "$failed" == 0 ]] || exit 1
