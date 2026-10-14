#!/usr/bin/env python3
"""Ramp concurrent chat POSTs (Scripted LLM + hybrid retrieval on Postgres) until SLO break."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TENANT = os.environ.get("TENANT_ID", "0a000000-0000-4000-a000-000000000001")
THREAD_ID = os.environ.get("THREAD_ID", "0a000000-0000-4000-a000-000000000030")
TOKEN = os.environ.get("DEMO_TOKEN", "token-a")
QUERIES = [
    "我们在哪家店吵的？",
    "7天无理由退货怎么规定？",
    "林夏住哪里？",
    "退货流程是什么？",
    "商场活动什么时候？",
]
STEP = int(os.environ.get("RETRIEVAL_STEP", "10"))
MAX_WORKERS = int(os.environ.get("RETRIEVAL_MAX_WORKERS", "120"))
REQUESTS_PER_LEVEL = int(os.environ.get("RETRIEVAL_REQUESTS", "40"))
FAIL_LIMIT = float(os.environ.get("RETRIEVAL_FAIL_RATE", "0.05"))
P95_LIMIT_MS = float(os.environ.get("RETRIEVAL_P95_LIMIT_MS", "8000"))
TIMEOUT_SEC = float(os.environ.get("RETRIEVAL_TIMEOUT_SEC", "60"))


def post_message(query: str) -> tuple[float, int]:
    body = json.dumps({"text": query}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/threads/{THREAD_ID}/messages",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Tenant-Id": TENANT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception:
        code = 0
    return (time.perf_counter() - start) * 1000, code


def run_level(workers: int) -> dict:
    latencies: list[float] = []
    errors = 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [
            pool.submit(post_message, QUERIES[i % len(QUERIES)])
            for i in range(REQUESTS_PER_LEVEL)
        ]
        for fut in as_completed(futs):
            ms, code = fut.result()
            latencies.append(ms)
            if code != 200:
                errors += 1
    elapsed = max(time.perf_counter() - t0, 1e-6)
    latencies.sort()
    p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0.0
    return {
        "workers": workers,
        "rps": round(REQUESTS_PER_LEVEL / elapsed, 2),
        "fail_rate": round(errors / REQUESTS_PER_LEVEL, 4),
        "p95_ms": round(p95, 1),
        "errors": errors,
    }


def main() -> int:
    print(f"=== Hybrid retrieval (HTTP chat path) ===\n{BASE_URL}  requests/level={REQUESTS_PER_LEVEL}")
    print(f"stop when fail>{FAIL_LIMIT} or p95>{P95_LIMIT_MS}ms\n")
    last_ok = 0
    for workers in range(STEP, MAX_WORKERS + 1, STEP):
        row = run_level(workers)
        print(
            f"workers={row['workers']:4d}  rps={row['rps']:6.2f}  "
            f"fail={row['fail_rate']:.3f}  p95_ms={row['p95_ms']:8.1f}  errors={row['errors']}"
        )
        if row["fail_rate"] <= FAIL_LIMIT and row["p95_ms"] <= P95_LIMIT_MS:
            last_ok = workers
            continue
        print(f">>> limit exceeded; last stable workers≈{last_ok}")
        break
    else:
        print(f">>> reached MAX_WORKERS={MAX_WORKERS} without threshold breach")
    return 0


if __name__ == "__main__":
    sys.exit(main())
