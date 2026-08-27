from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
LINXIA = "0a000000-0000-4000-a000-000000000010"


def _headers(token="token-a", tenant=TENANT):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant,
    }


def test_seed_eval_world_reloads_fixture_counts():
    client = TestClient(create_app(), raise_server_exceptions=False)
    seeded = client.post("/v1/eval/seed-world", headers=_headers())
    assert seeded.status_code == 200
    body = seeded.json()
    assert body["suite_version"] == "v1"
    assert body["persona_count"] >= 3
    assert body["memory_count"] >= 10


def test_persona_eval_run_generates_smoke_cases():
    client = TestClient(create_app(), raise_server_exceptions=False)
    started = client.post(
        f"/v1/personas/{LINXIA}/eval/runs",
        headers=_headers(),
        json={"strategy": "layered_tree"},
    )
    assert started.status_code == 202
    run_id = started.json()["id"]
    result = client.get(f"/v1/eval/runs/{run_id}", headers=_headers())
    assert result.status_code == 200
    body = result.json()
    assert body["strategy"] == "layered_tree"
    assert body["suite_version"] == "persona"
    assert body["metrics"]["tenant_leak_count"] == 0
    assert len(body["cases"]) >= 1


def test_list_recent_eval_runs_for_admin():
    client = TestClient(create_app(), raise_server_exceptions=False)
    started = client.post(
        "/v1/eval/runs",
        headers=_headers(),
        json={"strategy": "layered_tree", "suite_version": "v1", "mode": "retrieval"},
    )
    assert started.status_code == 202
    listed = client.get("/v1/eval/runs", headers=_headers(), params={"limit": 5})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(item["id"] == started.json()["id"] for item in items)


def test_member_cannot_list_eval_runs():
    client = TestClient(create_app(), raise_server_exceptions=False)
    listed = client.get("/v1/eval/runs", headers=_headers("token-member"))
    assert listed.status_code == 403
    assert listed.json()["error"]["code"] == "FORBIDDEN_WORKSPACE"
