#!/usr/bin/env python3
"""Concurrent layered_tree retrieve() against Postgres (fixture embed), no HTTP/LLM."""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient
from arbor.adapters.outbound.postgres import PostgresSession
from arbor.application.retrieval import retrieve
from arbor.domain.shared.ids import PersonaId, TenantId

DATABASE_URL = os.environ.get("DATABASE_URL", "")
TENANT = TenantId(os.environ.get("TENANT_ID", "0a000000-0000-4000-a000-000000000001"))
PERSONA = PersonaId(os.environ.get("PERSONA_ID", "0a000000-0000-4000-a000-000000000010"))
STRATEGY = os.environ.get("RETRIEVAL_STRATEGY", "layered_tree")
STEP = int(os.environ.get("RETRIEVAL_STEP", "8"))
MAX_WORKERS = int(os.environ.get("RETRIEVAL_MAX_WORKERS", "64"))
REQUESTS_PER_LEVEL = int(os.environ.get("RETRIEVAL_REQUESTS", "64"))
P95_LIMIT_MS = float(os.environ.get("RETRIEVAL_P95_LIMIT_MS", "3000"))
QUERIES = [
    "我们在哪家店吵的？",
    "7天无理由退货怎么规定？",
    "林夏住哪里？",
    "退货流程是什么？",
    "商场活动什么时候？",
]

_thread_local = __import__("threading").local()


def _session() -> PostgresSession:
    sess = getattr(_thread_local, "session", None)
    if sess is None:
        sess = PostgresSession.connect(DATABASE_URL, embed=FixtureEmbeddingClient())
        _thread_local.session = sess
    return sess


def _one_retrieve(query: str) -> float:
    session = _session()
    start = time.perf_counter()
    retrieve(
        strategy=STRATEGY,
        query=query,
        tenant_id=TENANT,
        persona_id=PERSONA,
        k=8,
        memories=session.memories.list_active(TENANT, PERSONA),
        events=session.events.list_nodes(TENANT, PERSONA),
        edges=session.events.list_edges(TENANT, PERSONA),
        summary=session.threads.summary_for(PERSONA),
        vector_search=session.vectors.search,
        embed=session.embed.embed,
        lexical_search=getattr(session.vectors, "lexical_search", None),
    )
    return (time.perf_counter() - start) * 1000


def run_level(workers: int) -> dict:
    latencies: list[float] = []
    errors = 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [
            pool.submit(_one_retrieve, QUERIES[i % len(QUERIES)])
            for i in range(REQUESTS_PER_LEVEL)
        ]
        for fut in as_completed(futs):
            try:
                latencies.append(fut.result())
            except Exception:
                errors += 1
    elapsed = max(time.perf_counter() - t0, 1e-6)
    latencies.sort()
    p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0.0
    return {
        "workers": workers,
        "rps": round(len(latencies) / elapsed, 2),
        "fail_rate": round(errors / REQUESTS_PER_LEVEL, 4),
        "p95_ms": round(p95, 1),
        "errors": errors,
    }


def main() -> int:
    if not DATABASE_URL:
        print("DATABASE_URL required", file=sys.stderr)
        return 1
    print(
        f"=== Hybrid retrieval (in-process {STRATEGY}) ===\n"
        f"requests/level={REQUESTS_PER_LEVEL}  stop p95>{P95_LIMIT_MS}ms\n"
    )
    last_ok = 0
    for workers in range(STEP, MAX_WORKERS + 1, STEP):
        row = run_level(workers)
        print(
            f"workers={row['workers']:4d}  rps={row['rps']:6.2f}  "
            f"fail={row['fail_rate']:.3f}  p95_ms={row['p95_ms']:8.1f}  errors={row['errors']}"
        )
        if row["fail_rate"] == 0 and row["p95_ms"] <= P95_LIMIT_MS:
            last_ok = workers
            continue
        print(f">>> limit exceeded; last stable workers≈{last_ok}")
        break
    else:
        print(f">>> reached MAX_WORKERS={MAX_WORKERS} without threshold breach")
    return 0


if __name__ == "__main__":
    sys.exit(main())
