from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"
ZHOU = "0a000000-0000-4000-a000-000000000020"
MEET = "0a000000-0000-4000-a000-000000000101"
CAPTION = "0a000000-0000-4000-a000-000000000306"
OLD_CAT = "0a000000-0000-4000-a000-000000000307"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_list_memories_filters_type_event_and_status():
    client = TestClient(create_app(), raise_server_exceptions=False)
    captions = client.get(
        f"/v1/personas/{LINXIA}/memories",
        headers=_headers(),
        params={"type": "image_caption"},
    )
    assert captions.status_code == 200
    ids = {item["id"] for item in captions.json()["items"]}
    assert ids == {CAPTION}
    assert captions.json()["items"][0]["type"] == "image_caption"
    by_event = client.get(
        f"/v1/personas/{LINXIA}/memories",
        headers=_headers(),
        params={"event_id": MEET},
    )
    assert {item["id"] for item in by_event.json()["items"]} == {CAPTION}
    superseded = client.get(
        f"/v1/personas/{LINXIA}/memories",
        headers=_headers(),
        params={"status": "superseded"},
    )
    assert {item["id"] for item in superseded.json()["items"]} == {OLD_CAT}
    defaulted = client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers())
    default_ids = {item["id"] for item in defaulted.json()["items"]}
    assert OLD_CAT not in default_ids
    assert CAPTION in default_ids
    assert defaulted.json()["total"] == len(defaulted.json()["items"])
    paged = client.get(
        f"/v1/personas/{LINXIA}/memories",
        headers=_headers(),
        params={"limit": 1, "offset": 0},
    )
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] > 1
    zhou = client.get(f"/v1/personas/{ZHOU}/memories", headers=_headers())
    assert all(item["id"].startswith("0a000000-0000-4000-a000-0000000004") for item in zhou.json()["items"])
    assert CAPTION not in {item["id"] for item in zhou.json()["items"]}


def test_list_memories_hidden_without_read_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers("token-member"))
    assert r.status_code in {403, 404}


def test_delete_memory_requires_admin_and_hides_from_active_list():
    client = TestClient(create_app(), raise_server_exceptions=False)
    denied = client.delete(
        f"/v1/personas/{LINXIA}/memories/{OLD_CAT}",
        headers=_headers("token-member"),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN_MEMORY_WRITE"

    removed = client.delete(
        f"/v1/personas/{LINXIA}/memories/{OLD_CAT}",
        headers=_headers(),
    )
    assert removed.status_code == 204
    superseded = client.get(
        f"/v1/personas/{LINXIA}/memories",
        headers=_headers(),
        params={"status": "superseded"},
    )
    assert OLD_CAT not in {item["id"] for item in superseded.json()["items"]}
    deleted = client.get(
        f"/v1/personas/{LINXIA}/memories",
        headers=_headers(),
        params={"status": "deleted"},
    )
    assert OLD_CAT in {item["id"] for item in deleted.json()["items"]}
