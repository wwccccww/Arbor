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
