#!/usr/bin/env bash
# Agent 生产化演示：一键启动工作台 + 离线证据链验证
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> 1/2 离线 demo-v1 证据链（12 步）"
python3 -m pytest tests/eval/test_demo_v1_smoke.py -q --tb=short

echo ""
echo "==> 2/2 启动工作台（UI 录屏彩排）"
echo "    打开 http://127.0.0.1:8000"
echo "    登录 demo-a@arbor.eval / arbor-owner"
echo "    按 docs/demo-script.md §Agent 生产化演示 操作"
echo ""
exec "$ROOT/scripts/run.sh"
