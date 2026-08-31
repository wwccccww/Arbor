from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"


def _headers(token: str = "token-a") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
    }


def test_agent_run_create_and_get():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={
            "goal": "查询退货政策",
            "plan_script": [
                {
                    "schema_version": 1,
                    "action": "retrieve",
                    "query": "退货政策",
                    "scopes": ["semantic_memory"],
                    "reason": "policy lookup",
                },
                {
                    "schema_version": 1,
                    "action": "answer",
                    "text": "7天无理由退货",
                    "citations": [],
                    "completion": True,
                },
            ],
        },
    )
    assert created.status_code == 202
    run_id = created.json()["id"]
    detail = client.get(f"/v1/agent-runs/{run_id}", headers=_headers())
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["id"] == run_id
    assert body["run"]["status"] in {"completed", "running", "pending", "failed"}
    assert body.get("step_tree") is not None
    request_id = body["run"].get("request_id") or (body["run"].get("metadata") or {}).get("request_id")
    assert request_id


def test_agent_run_missing_tenant_header():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers={"Authorization": "Bearer token-a"},
        json={"goal": "test"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"]


def test_agent_run_unauthenticated():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers={"X-Tenant-Id": TENANT},
        json={"goal": "test"},
    )
    assert response.status_code == 401


def test_approvals_forbidden_without_admin():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/v1/approvals", headers=_headers(token="token-b"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_WORKSPACE"


def test_agent_run_create_forbidden_plan_script(monkeypatch):
    monkeypatch.delenv("ARBOR_ALLOW_PLAN_SCRIPT", raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        f"/v1/personas/{LINXIA}/agent-runs",
        headers=_headers(),
        json={"goal": "test", "plan_script": [{"schema_version": 1, "action": "answer", "text": "x", "completion": True}]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_PLAN_SCRIPT"


def test_list_employee_definition_versions():
    client = TestClient(create_app(), raise_server_exceptions=False)
    listed = client.get(f"/v1/personas/{LINXIA}/employee-definitions", headers=_headers())
    assert listed.status_code == 200
    body = listed.json()
    assert isinstance(body.get("items"), list)
    assert len(body["items"]) >= 1


def test_employee_definition_and_eval_gate():
    client = TestClient(create_app(), raise_server_exceptions=False)
    definition = client.get(
        f"/v1/personas/{LINXIA}/employee-definition",
        headers=_headers(),
    )
    assert definition.status_code == 200
    payload = definition.json()
    assert payload["evaluation_suite"] == "agent-v1"
    assert payload.get("escalation_policy")

    eval_report = client.post(
        f"/v1/personas/{LINXIA}/employee-eval",
        headers=_headers(),
    )
    assert eval_report.status_code == 200
    report = eval_report.json()
    assert report.get("gate_passed") is True
    assert report.get("evaluation_suite") == "agent-v1"
