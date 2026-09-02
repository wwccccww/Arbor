#!/usr/bin/env bash
# A/B: default vs tuned retrieval on frozen ragas-official 100 (no --write-baseline).
set -euo pipefail
cd "$(dirname "$0")/.."

RUN_DATE="${RUN_DATE:-$(date -u +%Y-%m-%d)}"
export RUN_DATE
export ARBOR_GEN_MAX_WORKERS="${ARBOR_GEN_MAX_WORKERS:-4}"
export ARBOR_JUDGE_MAX_WORKERS="${ARBOR_JUDGE_MAX_WORKERS:-2}"
export ARBOR_JUDGE_TIMEOUT="${ARBOR_JUDGE_TIMEOUT:-600}"
export PYTHONUNBUFFERED=1

COMMON=(
  --suite ragas-official-v1
  --mode generation
  --strategy layered_tree
  --embed bge
)

run_arm() {
  local preset="$1"
  local run_id="${RUN_DATE}-${preset}"
  echo "=== ragas-official arm=${preset} run_id=${run_id} ==="
  python3 -m arbor.adapters.inbound.cli.eval_cli \
    "${COMMON[@]}" \
    --ragas-retrieval-preset "$preset" \
    --ragas-run-id "$run_id" \
    2>&1 | tee "/tmp/ragas-ab-${preset}.log"
}

run_arm default
run_arm tuned

python3 - <<'PY'
import json
import os
from pathlib import Path

from arbor.application.evaluation.ragas_pipeline import DEFAULT_RUNS_ROOT, build_report_from_artifacts

run_date = os.environ["RUN_DATE"]
keys = (
    "ragas_faithfulness",
    "ragas_context_recall",
    "ragas_context_precision",
    "ragas_answer_relevancy",
    "ragas_answer_correctness",
)
table: dict[str, dict] = {}
for preset in ("default", "tuned"):
    run_dir = DEFAULT_RUNS_ROOT / f"{run_date}-{preset}"
    report = build_report_from_artifacts(
        run_dir=run_dir,
        strategy="layered_tree",
        backend="auto",
        embed_label="bge-m3",
    )
    table[preset] = {k: (report.get("metrics") or {}).get(k) for k in keys}
    out = run_dir / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

print(json.dumps({"ab_compare": table, "run_date": run_date}, ensure_ascii=False, indent=2))
PY
