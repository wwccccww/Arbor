"""Concurrent hybrid retrieve() against Postgres (fixture embed), correctness smoke."""

from __future__ import annotations

import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient
from arbor.adapters.outbound.postgres import PostgresSession
from arbor.application.retrieval import retrieve
from arbor.domain.shared.ids import PersonaId, TenantId

pytestmark = pytest.mark.postgres

_TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
_PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")
_QUERIES = ("我们在哪家店吵的？", "7天无理由退货怎么规定？", "林夏住哪里？")
_local = threading.local()


def _db_url() -> str | None:
    from arbor.env import database_url

    return database_url() or os.environ.get("DATABASE_URL")


def _session(url: str) -> PostgresSession:
    sess = getattr(_local, "session", None)
    if sess is None:
        sess = PostgresSession.connect(url, embed=FixtureEmbeddingClient())
        _local.session = sess
    return sess


@pytest.mark.skipif(not _db_url(), reason="Postgres API needs DATABASE_URL")
def test_postgres_concurrent_hybrid_retrieve_no_errors():
    url = _db_url()
    assert url

    def one_retrieve(seed: int) -> None:
        session = _session(url)
        query = _QUERIES[seed % len(_QUERIES)]
        out = retrieve(
            strategy="layered_tree",
            query=query,
            tenant_id=_TENANT,
            persona_id=_PERSONA,
            k=8,
            memories=session.memories.list_active(_TENANT, _PERSONA),
            events=session.events.list_nodes(_TENANT, _PERSONA),
            edges=session.events.list_edges(_TENANT, _PERSONA),
            summary=session.threads.summary_for(_PERSONA),
            vector_search=session.vectors.search,
            embed=session.embed.embed,
            lexical_search=getattr(session.vectors, "lexical_search", None),
        )
        assert "hits" in out

    workers = 16
    total = 48
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one_retrieve, random.randint(0, 10_000)) for _ in range(total)]
        for fut in as_completed(futures):
            fut.result()
