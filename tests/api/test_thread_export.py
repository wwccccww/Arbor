from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
OTHER = "0b000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"
ZHOU = "0a000000-0000-4000-a000-000000000020"
LINXIA_THREAD = "0a000000-0000-4000-a000-000000000030"


def _headers(token="token-a", tenant=TENANT):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant,
    }


def test_export_thread_json_and_audit():
    client = TestClient(create_app(), raise_server_exceptions=False)
    chat = client.post(
        f"/v1/threads/{LINXIA_THREAD}/messages",
        headers=_headers(),
        json={"text": "还在吗"},
    )
    assert chat.status_code == 200
    exported = client.post(f"/v1/threads/{LINXIA_THREAD}/export", headers=_headers())
    assert exported.status_code == 200
    body = exported.json()
    assert body["id"] == LINXIA_THREAD
    assert body["persona_id"] == LINXIA
    contents = [item["content"] for item in body["messages"]]
    assert "还在吗" in contents
    logs = client.get("/v1/audit-logs", headers=_headers(), params={"action": "thread.export"})
    assert logs.status_code == 200
    items = logs.json()["items"]
    assert items
    assert items[0]["action"] == "thread.export"
    assert items[0]["payload"] == {"message_count": len(body["messages"])}
    assert "还在吗" not in str(items[0]["payload"])
    memories = client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers())
    assert all(item["text"] != "还在吗" for item in memories.json()["items"])


def test_export_hidden_without_chat_or_wrong_tenant():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(f"/v1/personas/{ZHOU}/threads", headers=_headers())
    assert created.status_code == 201
    zhou_thread = created.json()["id"]
    hidden = client.post(f"/v1/threads/{zhou_thread}/export", headers=_headers("token-member"))
    assert hidden.status_code == 404
    wrong = client.post(
        f"/v1/threads/{LINXIA_THREAD}/export",
        headers=_headers("token-member", tenant=OTHER),
    )
    assert wrong.status_code == 404
    allowed = client.post(f"/v1/threads/{LINXIA_THREAD}/export", headers=_headers("token-member"))
    assert allowed.status_code == 200
