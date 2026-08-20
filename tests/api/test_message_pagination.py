from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
ZHOU = "0a000000-0000-4000-a000-000000000020"
THREAD = "0a000000-0000-4000-a000-000000000030"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_list_messages_limit_offset_and_total():
    client = TestClient(create_app(), raise_server_exceptions=False)
    sent = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        json={"text": "还在吗"},
    )
    assert sent.status_code == 200
    full = client.get(f"/v1/threads/{THREAD}/messages", headers=_headers())
    assert full.status_code == 200
    assert full.json()["total"] == len(full.json()["items"])
    assert full.json()["total"] >= 2
    paged = client.get(
        f"/v1/threads/{THREAD}/messages",
        headers=_headers(),
        params={"limit": 1, "offset": 0},
    )
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] == full.json()["total"]
    created = client.post(f"/v1/personas/{ZHOU}/threads", headers=_headers())
    assert created.status_code == 201
    hidden = client.get(
        f"/v1/threads/{created.json()['id']}/messages",
        headers=_headers("token-member"),
    )
    assert hidden.status_code in {403, 404}
