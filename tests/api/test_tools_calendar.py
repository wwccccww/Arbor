from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_calendar_tool_requires_allowed_tool():
    client = TestClient(create_app(), raise_server_exceptions=False)
    denied = client.post(
        f"/v1/personas/{LINXIA}/tools/calendar",
        headers=_headers(),
        json={"query_text": "这周有什么安排"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN_TOOL"


def test_calendar_tool_stub_after_enabling_policy():
    client = TestClient(create_app(), raise_server_exceptions=False)
    patched = client.patch(
        f"/v1/personas/{LINXIA}",
        headers=_headers(),
        json={"tool_policy": {"allowed_tools": ["calendar"], "notes": "演示日历"}},
    )
    assert patched.status_code == 200
    created = client.post(
        f"/v1/personas/{LINXIA}/tools/calendar",
        headers=_headers(),
        json={"query_text": "近期日程"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["tool"] == "calendar"
    assert body.get("events") or body.get("summary")


def test_list_personas_include_stats():
    client = TestClient(create_app(), raise_server_exceptions=False)
    listed = client.get("/v1/personas?include_stats=true", headers=_headers())
    assert listed.status_code == 200
    linxia = next(item for item in listed.json()["items"] if item["id"] == LINXIA)
    stats = linxia.get("stats") or {}
    assert stats.get("memory_count", 0) >= 1
    assert "thread_count" in stats
