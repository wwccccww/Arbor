import json

from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
THREAD = "0a000000-0000-4000-a000-000000000030"
FILE_TEXT = "流式附件进Inbox"


def _headers():
    return {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": TENANT,
    }


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_stream_done_inbox_created_includes_attachment_parse():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        f"/v1/threads/{THREAD}/messages?stream=true",
        headers=_headers(),
        files={"file": ("note.txt", FILE_TEXT.encode(), "text/plain")},
        data={"text": "流式附件"},
    )
    assert response.status_code == 200
    done = next(event for event in _parse_sse(response.text) if event.get("type") == "done")
    assert done["inbox_created"] >= 1
    assert done.get("message_id")
