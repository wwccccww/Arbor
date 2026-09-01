import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.env import database_url
from tests.api.test_auth import _citation_ids

pytestmark = pytest.mark.postgres

_TENANT_HEADERS = {
    "Authorization": "Bearer token-a",
    "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
}


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres API needs DATABASE_URL")
def test_postgres_app_concurrent_me_with_tenant_header():
    """RLS middleware must not corrupt pooled transactions under parallel requests."""
    client = TestClient(
        create_app(database_url=database_url() or os.environ["DATABASE_URL"]),
        raise_server_exceptions=False,
    )

    def hit() -> int:
        return client.get("/v1/me", headers=_TENANT_HEADERS).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: hit(), range(24)))

    assert statuses.count(500) == 0
    assert all(code == 200 for code in statuses)


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


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres API needs DATABASE_URL")
def test_postgres_agent_run_survives_app_restart():
    """HTTP 创建的 Agent Run 在模拟进程重启（新 create_app）后仍可读取。"""
    db_url = database_url() or os.environ["DATABASE_URL"]
    headers = {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }
    persona_id = "0a000000-0000-4000-a000-000000000010"
    plan = [
        {
            "schema_version": 1,
            "action": "retrieve",
            "query": "退货政策",
            "scopes": ["semantic_memory"],
        },
        {
            "schema_version": 1,
            "action": "answer",
            "text": "7天无理由退货",
            "citations": [],
            "completion": True,
        },
    ]
    client1 = TestClient(create_app(database_url=db_url), raise_server_exceptions=False)
    created = client1.post(
        f"/v1/personas/{persona_id}/agent-runs",
        headers=headers,
        json={"goal": "PG 持久化验收", "plan_script": plan},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    detail1 = client1.get(f"/v1/agent-runs/{run_id}", headers=headers)
    assert detail1.status_code == 200
    goal = detail1.json()["run"]["goal"]

    client2 = TestClient(create_app(database_url=db_url), raise_server_exceptions=False)
    detail2 = client2.get(f"/v1/agent-runs/{run_id}", headers=headers)
    assert detail2.status_code == 200
    assert detail2.json()["run"]["goal"] == goal
    steps = client2.get(f"/v1/agent-runs/{run_id}/steps", headers=headers)
    assert steps.status_code == 200
    assert isinstance(steps.json().get("steps"), list)
