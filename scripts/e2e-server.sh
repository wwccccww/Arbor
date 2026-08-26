#!/usr/bin/env bash
# Start API with built web UI for Playwright smoke tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"
if [[ ! -d apps/web/dist ]]; then
  (cd apps/web && npm ci && npm run build)
fi
exec python3 -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8765
