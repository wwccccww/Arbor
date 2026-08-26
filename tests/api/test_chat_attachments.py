from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"
ZHOU = "0a000000-0000-4000-a000-000000000020"
THREAD = "0a000000-0000-4000-a000-000000000030"
FILE_TEXT = "聊天附件解析后进Inbox待确认"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_chat_multipart_file_parsed_to_inbox_not_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    before = {
        item["text"]
        for item in client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers()).json()["items"]
    }
    inbox_before = client.get(f"/v1/personas/{LINXIA}/inbox", headers=_headers())
    pending_before = {item["id"] for item in inbox_before.json()["items"]} if inbox_before.status_code == 200 else set()
    sent = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        files={"file": ("note.txt", FILE_TEXT.encode(), "text/plain")},
        data={"text": "看看这个"},
    )
    assert sent.status_code == 200
    assert sent.json()["attachments"] == [{"filename": "note.txt"}]
    history = client.get(f"/v1/threads/{THREAD}/messages", headers=_headers())
    assert history.status_code == 200
    user_msg = next(item for item in history.json()["items"] if item["role"] == "user" and item["content"] == "看看这个")
    assert user_msg["attachments"] == [{"filename": "note.txt"}]
    after = {
        item["text"]
        for item in client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers()).json()["items"]
    }
    assert FILE_TEXT not in after
    assert after == before
    inbox_after = client.get(f"/v1/personas/{LINXIA}/inbox", headers=_headers())
    assert inbox_after.status_code == 200
    new_items = [item for item in inbox_after.json()["items"] if item["id"] not in pending_before]
    assert any(FILE_TEXT in str(item.get("payload") or {}) for item in new_items)
    json_sent = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        json={"text": "只有文件名", "attachments": [{"filename": "shot.png"}]},
    )
    assert json_sent.status_code == 200
    assert json_sent.json()["attachments"] == [{"filename": "shot.png"}]


def test_chat_attachment_download_requires_chat():
    client = TestClient(create_app(), raise_server_exceptions=False)
    sent = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        files={"file": ("note.txt", FILE_TEXT.encode(), "text/plain")},
        data={"text": "看看这个"},
    )
    assert sent.status_code == 200
    downloaded = client.get(
        f"/v1/threads/{THREAD}/attachments/note.txt",
        headers=_headers(),
    )
    assert downloaded.status_code == 200
    assert downloaded.content == FILE_TEXT.encode()
    assert "note.txt" in downloaded.headers.get("content-disposition", "")
    member = client.get(
        f"/v1/threads/{THREAD}/attachments/note.txt",
        headers=_headers("token-member"),
    )
    assert member.status_code == 200
    assert member.content == FILE_TEXT.encode()
    missing = client.get(
        f"/v1/threads/{THREAD}/attachments/shot.png",
        headers=_headers(),
    )
    assert missing.status_code == 404
    created = client.post(f"/v1/personas/{ZHOU}/threads", headers=_headers())
    assert created.status_code == 201
    zhou_thread = created.json()["id"]
    hidden = client.get(
        f"/v1/threads/{zhou_thread}/attachments/note.txt",
        headers=_headers("token-member"),
    )
    assert hidden.status_code in {403, 404}
    wrong_tenant = client.get(
        f"/v1/threads/{THREAD}/attachments/note.txt",
        headers={
            "Authorization": "Bearer token-a",
            "X-Tenant-Id": "0b000000-0000-4000-a000-000000000001",
        },
    )
    assert wrong_tenant.status_code == 404


def test_chat_attachment_hidden_without_chat():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(f"/v1/personas/{ZHOU}/threads", headers=_headers())
    assert created.status_code == 201
    thread_id = created.json()["id"]
    hidden = client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=_headers("token-member"),
        files={"file": ("note.txt", b"secret", "text/plain")},
        data={"text": "看看"},
    )
    assert hidden.status_code in {403, 404}
