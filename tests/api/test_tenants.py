from fastapi.testclient import TestClient

from apps.api.main import create_app

TENANT = "0a000000-0000-4000-a000-000000000001"
OWNER = "0a000000-0000-4000-a000-000000000002"
MEMBER = "0a000000-0000-4000-a000-000000000003"


def _headers(token="token-a", tenant=TENANT):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant,
    }


def test_owner_lists_tenants_and_members():
    client = TestClient(create_app(), raise_server_exceptions=False)
    listed = client.get("/v1/tenants", headers={"Authorization": "Bearer token-a"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(item["id"] == TENANT and item["role"] == "owner" for item in items)
    me = client.get("/v1/me", headers={"Authorization": "Bearer token-a"})
    assert me.status_code == 200
    assert any(item["id"] == TENANT for item in me.json()["tenants"])
    members = client.get(f"/v1/tenants/{TENANT}/members", headers=_headers())
    assert members.status_code == 200
    emails = {item["user"]["email"] for item in members.json()["items"]}
    assert "demo-a@arbor.eval" in emails
    assert "member-a@arbor.eval" in emails


def test_create_tenant_and_invite_member():
    client = TestClient(create_app(), raise_server_exceptions=False)
    created = client.post(
        "/v1/tenants",
        headers={"Authorization": "Bearer token-a"},
        json={"name": "私人空间"},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "私人空间"
    assert created.json()["role"] == "owner"
    new_id = created.json()["id"]
    invited = client.post(
        f"/v1/tenants/{new_id}/members",
        headers=_headers(tenant=new_id),
        json={"email": "c@d.com", "role": "member"},
    )
    assert invited.status_code == 201
    assert invited.json()["user"]["email"] == "c@d.com"
    listed = client.get("/v1/tenants", headers={"Authorization": "Bearer token-a"})
    assert any(item["id"] == new_id for item in listed.json()["items"])


def test_member_cannot_manage_members():
    client = TestClient(create_app(), raise_server_exceptions=False)
    listed = client.get(f"/v1/tenants/{TENANT}/members", headers=_headers("token-member"))
    assert listed.status_code == 403
    spaces = client.get("/v1/tenants", headers={"Authorization": "Bearer token-member"})
    assert spaces.status_code == 200
    assert any(item["id"] == TENANT and item["role"] == "member" for item in spaces.json()["items"])
    invited = client.post(
        f"/v1/tenants/{TENANT}/members",
        headers=_headers("token-member"),
        json={"email": "x@y.com", "role": "member"},
    )
    assert invited.status_code == 403
    patched = client.patch(
        f"/v1/tenants/{TENANT}/members/{OWNER}",
        headers=_headers("token-member"),
        json={"role": "member"},
    )
    assert patched.status_code == 403


def test_cannot_demote_last_owner_over_http():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.patch(
        f"/v1/tenants/{TENANT}/members/{OWNER}",
        headers=_headers(),
        json={"role": "member"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "TENANT_OWNER_REQUIRED"
