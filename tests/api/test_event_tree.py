from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.adapters.outbound.inmemory import ScriptedReasoner


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }


LINXIA = "0a000000-0000-4000-a000-000000000010"
ZHOU_EVENT = "0a000000-0000-4000-a000-000000000201"
LINXIA_MEET = "0a000000-0000-4000-a000-000000000101"
LINXIA_FIGHT = "0a000000-0000-4000-a000-000000000102"
CAPTION = "0a000000-0000-4000-a000-000000000306"


def test_event_tree_stays_in_persona():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(f"/v1/personas/{LINXIA}/events/tree", headers=_headers())
    assert r.status_code == 200
    ids = {node["id"] for node in r.json()["nodes"]}
    assert LINXIA_FIGHT in ids
    assert ZHOU_EVENT not in ids
    fight = next(node for node in r.json()["nodes"] if node["id"] == LINXIA_FIGHT)
    assert "0a000000-0000-4000-a000-000000000303" in fight["memory_ids"]


def test_event_tree_hidden_without_read_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(f"/v1/personas/{LINXIA}/events/tree", headers=_headers("token-member"))
    assert r.status_code in {403, 404}


def test_confirm_mark_key_event_appears_on_tree():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="和好后去了西湖")),
        raise_server_exceptions=False,
    )
    client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "记一下"},
    )
    items = client.get(f"/v1/personas/{LINXIA}/inbox", headers=_headers()).json()["items"]
    confirmed = client.post(
        f"/v1/inbox/{items[0]['id']}/confirm",
        headers=_headers(),
        json={"mark_key_event": True},
    )
    assert confirmed.status_code == 200
    event_id = confirmed.json()["event_id"]
    tree = client.get(f"/v1/personas/{LINXIA}/events/tree", headers=_headers())
    ids = {node["id"] for node in tree.json()["nodes"]}
    assert event_id in ids
    created = next(node for node in tree.json()["nodes"] if node["id"] == event_id)
    assert created["type"] == "milestone"
    assert created["importance"] == 5
    assert confirmed.json()["id"] in created["memory_ids"]


def test_event_tree_rejects_unknown_view():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(
        f"/v1/personas/{LINXIA}/events/tree",
        headers=_headers(),
        params={"view": "graph"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_event_card_includes_related_memories():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get(f"/v1/events/{LINXIA_FIGHT}", headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == LINXIA_FIGHT
    assert body["title"] == "面店争吵"
    assert any(
        item["id"] == "0a000000-0000-4000-a000-000000000303"
        for item in (body["memories"] + body.get("verbatim") or [])
    )
    assert body["attachments"] == []
    meet = client.get(f"/v1/events/{LINXIA_MEET}", headers=_headers())
    assert meet.status_code == 200
    attachments = meet.json()["attachments"]
    assert {item["id"] for item in attachments} == {CAPTION}
    assert attachments[0]["type"] == "image_caption"
    assert CAPTION not in {item["id"] for item in meet.json()["memories"]}


def test_event_card_hidden_without_read_memory_and_wrong_tenant():
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get(f"/v1/events/{LINXIA_FIGHT}", headers=_headers("token-member")).status_code in {403, 404}
    wrong = client.get(
        f"/v1/events/{LINXIA_FIGHT}",
        headers={
            "Authorization": "Bearer token-a",
            "X-Tenant-Id": "0b000000-0000-4000-a000-000000000001",
        },
    )
    assert wrong.status_code == 404
