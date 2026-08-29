from fastapi.testclient import TestClient

from apps.api.main import create_app


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }


def test_health_and_ready():
    client = TestClient(create_app(), raise_server_exceptions=False)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True


def test_request_id_on_success_and_error():
    client = TestClient(create_app(), raise_server_exceptions=False)
    ok = client.get("/v1/me", headers=_headers())
    assert ok.status_code == 200
    request_id = ok.headers.get("X-Request-Id")
    assert request_id
    assert len(request_id) == 26

    err = client.get("/v1/me", headers={"Authorization": "Bearer bad"})
    assert err.status_code == 401
    assert err.headers.get("X-Request-Id")
    assert err.json()["error"]["request_id"] == err.headers.get("X-Request-Id")


def test_metrics_endpoint_available():
    client = TestClient(create_app(), raise_server_exceptions=False)
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "arbor_http_requests_total" in res.text


def test_chat_returns_decision_trace_and_debug_lookup():
    client = TestClient(create_app(), raise_server_exceptions=False)
    chat = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "你好"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body.get("request_id")
    assert body.get("decision_trace")
    assert chat.headers.get("X-Request-Id") == body["request_id"]

    debug = client.get(
        f"/v1/debug/requests/{body['request_id']}",
        headers=_headers(),
    )
    assert debug.status_code == 200
    assert debug.json()["decision_trace"]["generation"]["model"] == "scripted"
