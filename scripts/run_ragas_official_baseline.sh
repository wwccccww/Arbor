#!/usr/bin/env bash
# Re-run RAGAS official 100 with tuned retrieval + pipeline artifacts, then write baseline.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m arbor.adapters.inbound.cli.eval_cli \
  --suite ragas-official-v1 \
  --mode generation \
  --strategy layered_tree \
  --embed bge \
  --ragas-retrieval-preset tuned \
  --write-baseline \
  "$@"
