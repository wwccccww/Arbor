#!/usr/bin/env bash
# Smoke ragas-official: stratified N cases (default 20 = 10 single + 10 multi), generate + score.
# Review worst-cases.jsonl before running full 100-case baseline.
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT="${RAGAS_SMOKE_LIMIT:-20}"
RUN_ID="${RAGAS_SMOKE_RUN_ID:-smoke-$(date -u +%Y%m%d)-${LIMIT}}"
export ARBOR_GEN_MAX_WORKERS="${ARBOR_GEN_MAX_WORKERS:-4}"
export ARBOR_JUDGE_MAX_WORKERS="${ARBOR_JUDGE_MAX_WORKERS:-4}"
export ARBOR_JUDGE_TIMEOUT="${ARBOR_JUDGE_TIMEOUT:-600}"
export PYTHONUNBUFFERED=1

echo "ragas-official smoke: limit=${LIMIT} run_id=${RUN_ID} (stratified single/multi-hop)"

python3 -m arbor.adapters.inbound.cli.eval_cli \
  --suite ragas-official-v1 \
  --mode generation \
  --strategy layered_tree \
  --embed bge \
  --ragas-case-limit "$LIMIT" \
  --ragas-case-stratified \
  --ragas-run-id "$RUN_ID" \
  --ragas-worst-n "$LIMIT" \
  "$@"

echo "artifacts: eval/runs/ragas-official/${RUN_ID}/"
echo "review: eval/runs/ragas-official/${RUN_ID}/worst-cases.jsonl"
