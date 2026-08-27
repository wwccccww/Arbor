from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.adapters.outbound.inmemory import ScriptedReasoner

TENANT = "0a000000-0000-4000-a000-000000000001"
ZHOU = "0a000000-0000-4000-a000-000000000020"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_ticket_tool_requires_allowed_tool():
    client = TestClient(create_app(), raise_server_exceptions=False)
    denied = client.post(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/tools/ticket",
        headers=_headers(),
        json={"title": "空调坏了", "description": "面馆空调不制冷"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN_TOOL"


def test_ticket_tool_stub_after_enabling_policy():
    client = TestClient(create_app(), raise_server_exceptions=False)
    patched = client.patch(
        f"/v1/personas/{ZHOU}",
        headers=_headers(),
        json={"tool_policy": {"allowed_tools": ["ticket"], "notes": "演示工单"}},
    )
    assert patched.status_code == 200
    created = client.post(
        f"/v1/personas/{ZHOU}/tools/ticket",
        headers=_headers(),
        json={"title": "退货纠纷", "description": "客户要求加急处理"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["tool"] == "ticket"
    assert body["ticket_id"]
    assert "退货纠纷" in body.get("title", "")


def test_chat_heuristic_conflict_inbox():
    client = TestClient(
        create_app(reasoner=ScriptedReasoner(proposed_fact="林夏其实可以接受香菜")),
        raise_server_exceptions=False,
    )
    chat = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=_headers(),
        json={"text": "记一下香菜"},
    )
    assert chat.status_code == 200
    items = client.get(
        "/v1/personas/0a000000-0000-4000-a000-000000000010/inbox",
        headers=_headers(),
    ).json()["items"]
    conflict = next((item for item in items if item.get("kind") == "conflict"), None)
    assert conflict is not None
    assert conflict["conflicts_with"] == "0a000000-0000-4000-a000-000000000302"
