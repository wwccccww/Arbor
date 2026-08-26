from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
OTHER_TENANT = "0b000000-0000-4000-a000-000000000001"


def _headers(token="token-a", tenant=TENANT):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant,
    }


def test_owner_runs_retrieval_on_fixture_tenant():
    client = TestClient(create_app(), raise_server_exceptions=False)
    started = client.post(
        "/v1/eval/runs",
        headers=_headers(),
        json={"strategy": "layered_tree", "suite_version": "v1", "mode": "retrieval"},
    )
    assert started.status_code == 202
    run_id = started.json()["id"]
    result = client.get(f"/v1/eval/runs/{run_id}", headers=_headers())
    assert result.status_code == 200
    body = result.json()
    assert body["strategy"] == "layered_tree"
    assert body["suite_version"] == "v1"
    assert body["metrics"]["tenant_leak_count"] == 0
    assert body["p0_tenant_leak_zero"] is True


def test_member_cannot_start_or_read_eval():
    client = TestClient(create_app(), raise_server_exceptions=False)
    started = client.post(
        "/v1/eval/runs",
        headers=_headers("token-member"),
        json={"strategy": "layered_tree", "suite_version": "v1"},
    )
    assert started.status_code == 403
    assert started.json()["error"]["code"] == "FORBIDDEN_WORKSPACE"
    owner = client.post(
        "/v1/eval/runs",
        headers=_headers(),
        json={"strategy": "layered_tree", "suite_version": "v1"},
    )
    assert owner.status_code == 202
    hidden = client.get(f"/v1/eval/runs/{owner.json()['id']}", headers=_headers("token-member"))
    assert hidden.status_code == 403


def test_eval_run_hidden_from_other_tenant():
    client = TestClient(create_app(), raise_server_exceptions=False)
    started = client.post(
        "/v1/eval/runs",
        headers=_headers(),
        json={"strategy": "layered_tree", "suite_version": "v1"},
    )
    assert started.status_code == 202
    other = client.get(f"/v1/eval/runs/{started.json()['id']}", headers=_headers(tenant=OTHER_TENANT))
    assert other.status_code == 403
    assert other.json()["error"]["code"] == "FORBIDDEN_WORKSPACE"
