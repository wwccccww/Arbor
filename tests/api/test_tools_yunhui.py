from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
ZHOU = "0a000000-0000-4000-a000-000000000020"
LINXIA = "0a000000-0000-4000-a000-000000000010"


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_yunhui_order_requires_allowed_tool():
    client = TestClient(create_app(), raise_server_exceptions=False)
    denied = client.post(
        f"/v1/personas/{LINXIA}/tools/yunhui/orders",
        headers=_headers(),
        json={"order_id": "YH20260318001"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN_TOOL"


def test_yunhui_order_and_aftersale_stub():
    client = TestClient(create_app(), raise_server_exceptions=False)
    patched = client.patch(
        f"/v1/personas/{ZHOU}",
        headers=_headers(),
        json={"tool_policy": {"allowed_tools": ["order", "aftersale"], "notes": "云汇智选"}},
    )
    assert patched.status_code == 200
    found = client.post(
        f"/v1/personas/{ZHOU}/tools/yunhui/orders",
        headers=_headers(),
        json={"order_id": "YH20260318001"},
    )
    assert found.status_code == 200
    body = found.json()
    assert body["tool"] == "order"
    assert body["orders"][0]["status_label"] == "已发货"
    created = client.post(
        f"/v1/personas/{ZHOU}/tools/yunhui/aftersales",
        headers=_headers(),
        json={"order_id": "YH20260318001", "reason": "耳机有杂音", "kind": "return"},
    )
    assert created.status_code == 200
    assert created.json()["aftersale_id"] == "stub-as-001"
