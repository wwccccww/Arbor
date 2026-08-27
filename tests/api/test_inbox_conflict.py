from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.adapters.outbound.inmemory import ScriptedReasoner


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }


def _pending_inbox_id(client: TestClient) -> str:
    chat = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "记一下"},
    )
    assert chat.status_code == 200
    items = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    ).json()["items"]
    assert items
    return items[0]["id"]


def test_confirm_conflict_supersedes_old_memory():
    client = TestClient(
        create_app(
            reasoner=ScriptedReasoner(
                proposed_fact="林夏其实可以接受香菜",
                kind="conflict",
                conflicts_with="0a000000-0000-4000-a000-000000000302",
            )
        ),
        raise_server_exceptions=False,
    )
    cilantro = "0a000000-0000-4000-a000-000000000302"
    inbox_id = _pending_inbox_id(client)
    inbox = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    ).json()["items"]
    conflict_item = next(item for item in inbox if item["id"] == inbox_id)
    assert conflict_item["kind"] == "conflict"
    assert conflict_item["conflicts_with"] == cilantro

    before = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/memories",
        headers=_headers(),
    ).json()["items"]
    assert any(item["id"] == cilantro for item in before)

    confirmed = client.post(f"/v1/inbox/{inbox_id}/confirm", headers=_headers())
    assert confirmed.status_code == 200
    new_id = confirmed.json()["id"]

    superseded = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/memories",
        headers=_headers(),
        params={"status": "superseded"},
    ).json()["items"]
    assert cilantro in {item["id"] for item in superseded}

    active = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/memories",
        headers=_headers(),
    ).json()["items"]
    assert cilantro not in {item["id"] for item in active}
    assert new_id in {item["id"] for item in active}


def test_confirm_twice_is_conflict():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="只能确认一次")),
        raise_server_exceptions=False,
    )
    inbox_id = _pending_inbox_id(client)
    first = client.post(f"/v1/inbox/{inbox_id}/confirm", headers=_headers())
    assert first.status_code == 200
    second = client.post(f"/v1/inbox/{inbox_id}/confirm", headers=_headers())
    assert second.status_code == 409
    err = second.json()["error"]
    assert err["code"] == "CONFLICT_INBOX_STATE"
    assert len(err["request_id"]) == 26


def test_dismiss_after_confirm_is_conflict():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="确认后不能忽略")),
        raise_server_exceptions=False,
    )
    inbox_id = _pending_inbox_id(client)
    assert client.post(f"/v1/inbox/{inbox_id}/confirm", headers=_headers()).status_code == 200
    dismissed = client.post(f"/v1/inbox/{inbox_id}/dismiss", headers=_headers())
    assert dismissed.status_code == 409
    assert dismissed.json()["error"]["code"] == "CONFLICT_INBOX_STATE"
