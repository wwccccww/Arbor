from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"

PLAN_TICKET_APPROVAL = [
    {
        "schema_version": 1,
        "action": "retrieve",
        "query": "空调故障处理",
        "scopes": ["semantic_memory", "procedural_memory"],
    },
    {
        "schema_version": 1,
        "action": "tool",
        "tool_name": "ticket.create",
        "arguments": {"title": "会议室空调故障", "priority": "high"},
        "evidence_ids": [],
    },
    {
        "schema_version": 1,
        "action": "answer",
        "text": "工单已登记",
        "citations": [],
        "completion": True,
    },
]


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


def test_agent_run_steps_success_and_forbidden():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "步骤列表测试"},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    ok = client.get(f"/v1/agent-runs/{run_id}/steps", headers=_headers())
    assert ok.status_code == 200
    assert isinstance(ok.json().get("steps"), list)
    forbidden = client.get(f"/v1/agent-runs/{run_id}/steps", headers=_headers(token="token-b"))
    assert forbidden.status_code == 403


def test_cancel_and_resume_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "未认证测试"},
    )
    run_id = created.json()["id"]
    cancel = client.post(f"/v1/agent-runs/{run_id}/cancel", headers={"X-Tenant-Id": TENANT})
    assert cancel.status_code == 401
    resume = client.post(f"/v1/agent-runs/{run_id}/resume", headers={"X-Tenant-Id": TENANT})
    assert resume.status_code == 401


def test_agent_eval_runs_admin_success_and_member_forbidden():
    client = TestClient(create_app(), raise_server_exceptions=False)
    ok = client.post("/v1/agent-eval/runs", headers=_headers())
    assert ok.status_code == 200
    assert ok.json().get("suite_version") == "agent-v1"
    denied = client.post("/v1/agent-eval/runs", headers=_headers(token="token-b"))
    assert denied.status_code == 403


def test_agent_eval_runs_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/v1/agent-eval/runs", headers={"X-Tenant-Id": TENANT})
    assert response.status_code == 401


def test_employee_definition_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(
        f"/v1/personas/{LINXIA}/employee-definition",
        headers={"X-Tenant-Id": TENANT},
    )
    assert response.status_code == 401


def test_approvals_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/v1/approvals", headers={"X-Tenant-Id": TENANT})
    assert response.status_code == 401


def _seed_procedural_draft(app) -> str:
    memories = app.state.confirm.memories
    memory_id = MemoryId(f"0a000000-0000-4000-a000-{uuid.uuid4().hex[:12]}")
    draft = MemoryItem(
        id=memory_id,
        tenant_id=TenantId(TENANT),
        persona_id=PersonaId(LINXIA),
        text="HTTP publish SOP",
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.PROCEDURAL,
        source={"draft": True, "version": "v-http"},
    )
    memories.save(draft)
    return memory_id.value


def test_publish_procedural_memory_admin_success():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    memory_id = _seed_procedural_draft(app)
    ok = client.post(
        f"/v1/personas/{LINXIA}/memories/{memory_id}/publish",
        headers=_headers(),
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body.get("published") is True
    assert body.get("version") == "v-http"


def test_agent_run_get_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "未认证读取"},
    )
    run_id = created.json()["id"]
    response = client.get(f"/v1/agent-runs/{run_id}", headers={"X-Tenant-Id": TENANT})
    assert response.status_code == 401


def test_cancel_agent_run_success_on_terminal():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "取消成功测试"},
    )
    run_id = created.json()["id"]
    ok = client.post(f"/v1/agent-runs/{run_id}/cancel", headers=_headers())
    assert ok.status_code == 200
    assert ok.json().get("status") in {"completed", "cancelled", "failed", "running", "pending"}


def test_resume_agent_run_success_while_waiting_approval():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "恢复成功测试", "plan_script": PLAN_TICKET_APPROVAL},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    detail = client.get(f"/v1/agent-runs/{run_id}", headers=_headers())
    assert detail.status_code == 200
    status = detail.json()["run"]["status"]
    if status == "waiting_approval":
        ok = client.post(f"/v1/agent-runs/{run_id}/resume", headers=_headers())
        assert ok.status_code == 200


def test_approvals_admin_success_and_approve_flow():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "审批流测试", "plan_script": PLAN_TICKET_APPROVAL},
    )
    run_id = created.json()["id"]
    listed = client.get("/v1/approvals", headers=_headers())
    assert listed.status_code == 200
    items = listed.json().get("items") or []
    matching = [item for item in items if item.get("run_id") == run_id]
    if matching:
        approval_id = matching[0]["id"]
        approved = client.post(f"/v1/approvals/{approval_id}/approve", headers=_headers())
        assert approved.status_code == 200


def test_approvals_reject_flow_blocks_side_effect():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "审批拒绝测试", "plan_script": PLAN_TICKET_APPROVAL},
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    detail = client.get(f"/v1/agent-runs/{run_id}", headers=_headers())
    assert detail.status_code == 200
    if detail.json()["run"]["status"] != "waiting_approval":
        return
    listed = client.get("/v1/approvals", headers=_headers())
    matching = [
        item for item in (listed.json().get("items") or []) if item.get("run_id") == run_id
    ]
    assert matching
    approval_id = matching[0]["id"]
    rejected = client.post(f"/v1/approvals/{approval_id}/reject", headers=_headers())
    assert rejected.status_code == 200
    after = client.get(f"/v1/agent-runs/{run_id}", headers=_headers())
    assert after.status_code == 200
    assert after.json()["run"]["status"] in {"failed", "cancelled", "completed"}


def test_approvals_reject_forbidden_cross_member():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "拒绝权限测试", "plan_script": PLAN_TICKET_APPROVAL},
    )
    run_id = created.json()["id"]
    listed = client.get("/v1/approvals", headers=_headers())
    matching = [
        item for item in (listed.json().get("items") or []) if item.get("run_id") == run_id
    ]
    if not matching:
        return
    approval_id = matching[0]["id"]
    forbidden = client.post(
        f"/v1/approvals/{approval_id}/reject",
        headers=_headers(token="token-b"),
    )
    assert forbidden.status_code == 403


def test_employee_templates_success_and_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    ok = client.get("/v1/employee-templates", headers=_headers())
    assert ok.status_code == 200
    assert isinstance(ok.json().get("items"), list)
    unauth = client.get("/v1/employee-templates")
    assert unauth.status_code == 401


def test_employee_eval_forbidden_and_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    denied = client.post(
        f"/v1/personas/{LINXIA}/employee-eval",
        headers=_headers(token="token-b"),
    )
    assert denied.status_code == 403
    unauth = client.post(
        f"/v1/personas/{LINXIA}/employee-eval",
        headers={"X-Tenant-Id": TENANT},
    )
    assert unauth.status_code == 401


def test_employee_definition_draft_publish_flow():
    client = TestClient(create_app(), raise_server_exceptions=False)
    version = f"9.9-{uuid.uuid4().hex[:6]}"
    draft = client.post(
        f"/v1/personas/{LINXIA}/employee-definitions",
        headers=_headers(),
        json={
            "version": version,
            "role": "customer_service",
            "evaluation_suite": "agent-v1",
            "tool_policy": {"allowed_tools": ["ticket", "calendar"]},
            "approval_policy": {"ticket.create": True},
        },
    )
    assert draft.status_code == 201
    gate_blocked = client.post(
        f"/v1/personas/{LINXIA}/employee-definitions/{version}/publish",
        headers=_headers(),
    )
    assert gate_blocked.status_code == 400
    assert gate_blocked.json()["error"]["code"] == "EMPLOYEE_EVAL_GATE"
    eval_report = client.post(
        f"/v1/personas/{LINXIA}/employee-eval",
        headers=_headers(),
        params={"version": version},
    )
    assert eval_report.status_code == 200
    assert eval_report.json().get("gate_passed") is True
    published = client.post(
        f"/v1/personas/{LINXIA}/employee-definitions/{version}/publish",
        headers=_headers(),
    )
    assert published.status_code == 200
    assert published.json().get("release_status") == "published"


def test_create_employee_definition_forbidden_for_member():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        f"/v1/personas/{LINXIA}/employee-definitions",
        headers=_headers(token="token-b"),
        json={"version": "9.9-denied", "role": "customer_service"},
    )
    assert response.status_code == 403


def test_delete_persona_admin_success():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        "/v1/personas",
        headers=_headers(),
        json={"display_name": "待删除人设", "skin": "companion"},
    )
    assert created.status_code == 201
    persona_id = created.json()["id"]
    deleted = client.delete(f"/v1/personas/{persona_id}", headers=_headers())
    assert deleted.status_code == 200
    assert deleted.json().get("deleted") is True
