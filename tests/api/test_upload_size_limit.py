from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"
THREAD = "0a000000-0000-4000-a000-000000000030"


def _headers():
    return {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": TENANT,
    }


def test_upload_rejects_oversize_import_and_chat():
    client = TestClient(create_app(max_upload_bytes=8), raise_server_exceptions=False)
    too_big = b"123456789"
    before = client.app.state.storage.count()
    imported = client.post(
        f"/v1/personas/{LINXIA}/imports",
        headers=_headers(),
        files={"file": ("big.txt", too_big, "text/plain")},
    )
    assert imported.status_code == 400
    assert imported.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.app.state.storage.count() == before
    chat = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        files={"file": ("big.txt", too_big, "text/plain")},
        data={"text": "看看"},
    )
    assert chat.status_code == 400
    assert chat.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.app.state.storage.count() == before
    ok = client.post(
        f"/v1/personas/{LINXIA}/imports",
        headers=_headers(),
        files={"file": ("ok.txt", b"12345678", "text/plain")},
    )
    assert ok.status_code == 202
    assert client.app.state.storage.count() == before + 1
