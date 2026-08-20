from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_auth_missing_bearer():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_error_shape():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/v1/me")
    err = r.json()["error"]
    assert "code" in err and "message" in err and "request_id" in err


def test_memory_hidden_without_grant():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/memories",
        headers={
            "Authorization": "Bearer token-member",
            "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
        },
    )
    assert r.status_code in {403, 404}


def test_tenant_mismatch_not_found():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010",
        headers={
            "Authorization": "Bearer token-a",
            "X-Tenant-Id": "0b000000-0000-4000-a000-000000000001",
        },
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_chat_citations_subset_of_injected():
    client = TestClient(create_app(extra_citation="0dead000-0000-4000-a000-000000000001"), raise_server_exceptions=False)
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
    injected = set(body["injected_memory_ids"])
    assert set(body["citations"]) <= injected
    assert "0dead000-0000-4000-a000-000000000001" not in body["citations"]


def test_grants_revoke_chat():
    client = TestClient(create_app(), raise_server_exceptions=False)
    headers = {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }
    client.put(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/grants",
        headers=headers,
        json={"grants": []},
    )
    r = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers={
            "Authorization": "Bearer token-member",
            "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
        },
        json={"text": "还在吗"},
    )
    assert r.status_code in {403, 404}
