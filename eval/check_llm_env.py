#!/usr/bin/env python3
"""检查评测 LLM 环境：不打印密钥。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
print("DEEPSEEK_API_KEY", "set" if os.environ.get("DEEPSEEK_API_KEY") else "missing")
print("OPENAI_API_KEY", "set" if os.environ.get("OPENAI_API_KEY") else "missing")
print("key_length", len(key))

try:
    import ragas
    from ragas.testset import TestsetGenerator  # noqa: F401

    print("ragas_import", "ok", ragas.__version__)
except Exception as exc:  # noqa: BLE001
    print("ragas_import", "fail", type(exc).__name__, str(exc)[:200])
    return_code = 2
else:
    return_code = 0 if key else 1

if key:
    try:
        import httpx

        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat"),
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 4,
            },
            timeout=30.0,
        )
        print("deepseek_http", r.status_code)
        if r.status_code >= 400:
            print("deepseek_error", r.text[:200])
            return_code = 3
    except Exception as exc:  # noqa: BLE001
        print("deepseek_http", "fail", type(exc).__name__)
        return_code = 3
else:
    print("deepseek_http", "skipped")

raise SystemExit(return_code)
