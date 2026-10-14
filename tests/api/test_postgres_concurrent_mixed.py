"""Mixed read-only HTTP concurrency against Postgres-backed API."""

from __future__ import annotations

import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.env import database_url

pytestmark = pytest.mark.postgres

_TENANT = "0a000000-0000-4000-a000-000000000001"
_HEADERS = {
    "Authorization": "Bearer token-a",
    "X-Tenant-Id": _TENANT,
}
_PERSONA = "0a000000-0000-4000-a000-000000000010"
_THREAD = "0a000000-0000-4000-a000-000000000030"


def _db_url() -> str | None:
    return database_url() or os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not _db_url(), reason="Postgres API needs DATABASE_URL")
def test_postgres_mixed_readonly_concurrent_no_500():
    """RLS + pool under mixed parallel read traffic (smoke, not capacity proof)."""
    client = TestClient(create_app(database_url=_db_url()), raise_server_exceptions=False)

    def one_request(seed: int) -> int:
        choice = seed % 3
        if choice == 0:
            return client.get("/v1/me", headers=_HEADERS).status_code
        if choice == 1:
            return client.get("/v1/personas", headers=_HEADERS).status_code
        return client.get(f"/v1/threads/{_THREAD}/messages", headers=_HEADERS).status_code

    workers = 32
    total = 96
    statuses: list[int] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one_request, random.randint(0, 10_000)) for _ in range(total)]
        for fut in as_completed(futures):
            statuses.append(fut.result())

    assert statuses.count(500) == 0
    assert all(code in {200, 404} for code in statuses), statuses
