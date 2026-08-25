from fastapi.testclient import TestClient

from apps.api.main import create_app

HEADERS = {
    "Authorization": "Bearer token-a",
    "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
}
THREAD = "0a000000-0000-4000-a000-000000000030"


def test_message_history_citations_keep_event_id_for_jump():
    """Reloading a thread must return the same jumpable citation shape as POST."""
    client = TestClient(create_app(), raise_server_exceptions=False)
    posted = client.post(
        f"/v1/threads/{THREAD}/messages",
        headers=HEADERS,
        json={"text": "我们在哪家店吵的？"},
    )
    assert posted.status_code == 200
    live = posted.json()["citations"]
    assert live
    assert all(isinstance(item, dict) for item in live)
    live_with_event = [item for item in live if item.get("event_id")]
    assert live_with_event, "fixture reply should cite a memory linked to an event"

    history = client.get(f"/v1/threads/{THREAD}/messages", headers=HEADERS)
    assert history.status_code == 200
    items = history.json()["items"]
    assistant = next(item for item in reversed(items) if item["role"] == "assistant")
    stored = assistant["citations"]
    assert stored
    for expected in live_with_event:
        match = next(item for item in stored if item.get("memory_id") == expected["memory_id"])
        assert match.get("event_id") == expected["event_id"]
        assert match.get("preview")
