#!/usr/bin/env bash
# One-command local workbench.
# Usage: ./scripts/run.sh
# Then open http://127.0.0.1:8000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已复制 .env.example -> .env，请填入 DEEPSEEK_API_KEY 后再开真实对话。"
fi

if ! grep -qE '^DEEPSEEK_API_KEY=.+' .env || grep -qE '^DEEPSEEK_API_KEY=\s*$' .env; then
  echo "未检测到 DEEPSEEK_API_KEY：对话将使用脚本回复。到 https://platform.deepseek.com 创建密钥后写入 .env。"
fi

python3 -m pip install -e ".[api,postgres]"
(cd apps/web && npm install && npm run build)
exec python3 -m uvicorn apps.api.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
