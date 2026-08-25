import os

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.env import database_url
from tests.api.test_auth import _citation_ids

pytestmark = pytest.mark.postgres


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres API needs DATABASE_URL")
def test_postgres_app_unauthenticated():
    client = TestClient(
        create_app(database_url=database_url() or os.environ["DATABASE_URL"]),
        raise_server_exceptions=False,
    )
    r = client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres API needs DATABASE_URL")
def test_postgres_app_chat_citations_subset():
    client = TestClient(
        create_app(database_url=database_url() or os.environ["DATABASE_URL"]),
        raise_server_exceptions=False,
    )
    r = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers={
            "Authorization": "Bearer token-a",
            "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
        },
        json={"text": "我们在哪家店吵的？"},
    )
    assert r.status_code == 200
    body = r.json()
    assert _citation_ids(body) <= set(body["injected_memory_ids"])
    assert body["role"] == "assistant"
    assert body["message_id"]
