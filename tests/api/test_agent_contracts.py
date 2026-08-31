from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"


def _headers(token: str = "token-a") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_list_agent_runs_success_and_forbidden():
    client = TestClient(create_app(), raise_server_exceptions=False)
    ok = client.get(f"/v1/personas/{LINXIA}/agent-runs", headers=_headers())
    assert ok.status_code == 200
    assert isinstance(ok.json().get("items"), list)
    denied = client.get(f"/v1/personas/{LINXIA}/agent-runs", headers=_headers(token="token-b"))
    assert denied.status_code == 403


def test_list_agent_runs_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(f"/v1/personas/{LINXIA}/agent-runs", headers={"X-Tenant-Id": TENANT})
    assert response.status_code == 401


def test_agent_run_get_forbidden_cross_member():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "只读测试"},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    forbidden = client.get(f"/v1/agent-runs/{run_id}", headers=_headers(token="token-b"))
    assert forbidden.status_code == 403


def test_employee_definitions_forbidden_without_access():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(
        f"/v1/personas/{LINXIA}/employee-definitions",
        headers=_headers(token="token-b"),
    )
    assert response.status_code == 403


def test_cancel_agent_run_forbidden_cross_member():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "取消权限测试"},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    forbidden = client.post(
        f"/v1/agent-runs/{run_id}/cancel",
        headers=_headers(token="token-b"),
    )
    assert forbidden.status_code == 403


def test_resume_agent_run_forbidden_cross_member():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "恢复权限测试"},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    forbidden = client.post(
        f"/v1/agent-runs/{run_id}/resume",
        headers=_headers(token="token-b"),
    )
    assert forbidden.status_code == 403


def test_publish_procedural_memory_forbidden_without_access():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        f"/v1/personas/{LINXIA}/memories/00000000-0000-4000-a000-000000000099/publish",
        headers=_headers(token="token-b"),
    )
    assert response.status_code in {403, 404}


def test_delete_persona_forbidden_without_admin():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.delete(
        f"/v1/personas/{LINXIA}",
        headers=_headers(token="token-b"),
    )
    assert response.status_code == 403
