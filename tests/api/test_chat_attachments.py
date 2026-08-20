from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"
ZHOU = "0a000000-0000-4000-a000-000000000020"
THREAD = "0a000000-0000-4000-a000-000000000030"
FILE_TEXT = "聊天附件不该进记忆也不该进Inbox"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_chat_multipart_file_stays_off_memory():
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
    if inbox_after.status_code == 200:
        for item in inbox_after.json()["items"]:
            if item["id"] in pending_before:
                continue
            assert FILE_TEXT not in str(item.get("payload") or {})
    json_sent = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        json={"text": "只有文件名", "attachments": [{"filename": "shot.png"}]},
    )
    assert json_sent.status_code == 200
    assert json_sent.json()["attachments"] == [{"filename": "shot.png"}]


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
