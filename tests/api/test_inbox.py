from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.adapters.outbound.inmemory import ScriptedReasoner


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }


def test_extract_goes_to_inbox_then_confirm():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="林夏最近开始喝美式")),
        raise_server_exceptions=False,
    )
    chat = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "我最近喜欢喝美式"},
    )
    assert chat.status_code == 200
    assert chat.json()["inbox_created"] == 1

    listed = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["payload"]["text"] == "林夏最近开始喝美式"

    confirmed = client.post(f"/v1/inbox/{items[0]['id']}/confirm", headers=_headers())
    assert confirmed.status_code == 200
    empty = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    )
    assert empty.json()["items"] == []


def test_inbox_hidden_without_write_memory():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="不该被 member 看见")),
        raise_server_exceptions=False,
    )
    client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "记一下"},
    )
    r = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers("token-member"),
    )
    assert r.status_code in {403, 404}


def test_inbox_dismiss():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="可忽略的候选")),
        raise_server_exceptions=False,
    )
    client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "记一下"},
    )
    items = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    ).json()["items"]
    r = client.post(f"/v1/inbox/{items[0]['id']}/dismiss", headers=_headers())
    assert r.status_code == 200
    leftover = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    )
    assert leftover.json()["items"] == []
