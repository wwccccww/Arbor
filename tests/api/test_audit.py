from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.adapters.outbound.inmemory import ScriptedReasoner

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_audit_records_persona_import_and_confirm():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="林夏开始喝美式")),
        raise_server_exceptions=False,
    )
    patched = client.patch(
        f"/v1/personas/{LINXIA}",
        headers=_headers(),
        json={"one_liner": "改过一句"},
    )
    assert patched.status_code == 200
    uploaded = client.post(
        f"/v1/personas/{LINXIA}/imports",
        headers=_headers(),
        files={"file": ("notes.txt", b"linxia", "text/plain")},
    )
    assert uploaded.status_code == 202
    chat = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "记一下"},
    )
    assert chat.status_code == 200
    inbox = client.get(f"/v1/personas/{LINXIA}/inbox", headers=_headers())
    inbox_id = inbox.json()["items"][0]["id"]
    confirmed = client.post(f"/v1/inbox/{inbox_id}/confirm", headers=_headers())
    assert confirmed.status_code == 200
    logs = client.get("/v1/audit-logs", headers=_headers())
    assert logs.status_code == 200
    actions = [item["action"] for item in logs.json()["items"]]
    assert "persona.update" in actions
    assert "memory.import" in actions
    assert "memory.confirm" in actions
    persona_only = client.get("/v1/audit-logs", headers=_headers(), params={"action": "persona.update"})
    assert {item["action"] for item in persona_only.json()["items"]} == {"persona.update"}
    assert all(item["persona_id"] == LINXIA for item in persona_only.json()["items"])
    payload = persona_only.json()["items"][0]["payload"]
    assert "taboos" not in payload or payload.get("fields") == ["one_liner"]
    assert payload.get("fields") == ["one_liner"]


def test_member_cannot_read_audit_logs():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/v1/audit-logs", headers=_headers("token-member"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN_WORKSPACE"
