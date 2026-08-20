from fastapi.testclient import TestClient

from apps.api.main import create_app


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }


LINXIA = "0a000000-0000-4000-a000-000000000010"
ZHOU = "0a000000-0000-4000-a000-000000000020"
THREAD = "0a000000-0000-4000-a000-000000000030"


def test_owner_lists_all_personas_member_only_granted():
    client = TestClient(create_app(), raise_server_exceptions=False)
    owner = client.get("/v1/personas", headers=_headers())
    assert owner.status_code == 200
    owner_ids = {item["id"] for item in owner.json()["items"]}
    assert {LINXIA, ZHOU} <= owner_ids
    member = client.get("/v1/personas", headers=_headers("token-member"))
    member_ids = {item["id"] for item in member.json()["items"]}
    assert LINXIA in member_ids
    assert ZHOU not in member_ids


def test_persona_hides_taboos_without_read_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    owner = client.get(f"/v1/personas/{LINXIA}", headers=_headers())
    assert owner.status_code == 200
    assert "香菜" in owner.json()["taboos"]
    member = client.get(f"/v1/personas/{LINXIA}", headers=_headers("token-member"))
    assert member.status_code == 200
    assert "taboos" not in member.json()
    assert member.json()["display_name"] == "林夏"


def test_create_patch_persona_and_thread_history():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        "/v1/personas",
        headers=_headers(),
        json={"skin": "companion", "display_name": "新林夏", "one_liner": "新档案", "taboos": ["香菜"]},
    )
    assert created.status_code == 201
    persona_id = created.json()["id"]
    patched = client.patch(
        f"/v1/personas/{persona_id}",
        headers=_headers(),
        json={"one_liner": "更新后的一句话"},
    )
    assert patched.status_code == 200
    assert patched.json()["one_liner"] == "更新后的一句话"
    thread = client.post(f"/v1/personas/{persona_id}/threads", headers=_headers())
    assert thread.status_code == 201
    thread_id = thread.json()["id"]
    listed = client.get(f"/v1/personas/{persona_id}/threads", headers=_headers())
    assert any(item["id"] == thread_id for item in listed.json()["items"])
    chat = client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=_headers(),
        json={"text": "还在吗"},
    )
    assert chat.status_code == 200
    history = client.get(f"/v1/threads/{thread_id}/messages", headers=_headers())
    assert history.status_code == 200
    roles = [item["role"] for item in history.json()["items"]]
    assert roles == ["user", "assistant"]
    assert history.json()["items"][0]["content"] == "还在吗"


def test_member_cannot_create_persona_or_read_zhou():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        "/v1/personas",
        headers=_headers("token-member"),
        json={"skin": "companion", "display_name": "不该创建"},
    )
    assert created.status_code == 403
    hidden = client.get(f"/v1/personas/{ZHOU}", headers=_headers("token-member"))
    assert hidden.status_code in {403, 404}


def test_existing_thread_history_endpoint():
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        json={"text": "我们上次为什么吵架？"},
    )
    history = client.get(f"/v1/threads/{THREAD}/messages", headers=_headers())
    assert history.status_code == 200
    assert len(history.json()["items"]) >= 2
