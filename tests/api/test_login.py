from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_login_issues_tokens_and_me_works():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.post("/v1/auth/login", json={"email": "demo-a@arbor.eval", "password": "arbor-owner"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "demo-a@arbor.eval"
    assert body["access_token"]
    assert body["refresh_token"]
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "demo-a@arbor.eval"


def test_login_rejects_bad_password():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.post("/v1/auth/login", json={"email": "demo-a@arbor.eval", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_refresh_rotates_and_logout_revokes():
    client = TestClient(create_app(), raise_server_exceptions=False)
    login = client.post(
        "/v1/auth/login",
        json={"email": "member-a@arbor.eval", "password": "arbor-member"},
    ).json()
    old_access = login["access_token"]
    refreshed = client.post("/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["access_token"] != old_access
    stale = client.get("/v1/me", headers={"Authorization": f"Bearer {old_access}"})
    assert stale.status_code == 401
    ok = client.get("/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert ok.status_code == 200
    client.post("/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    again = client.post("/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert again.status_code == 401


def test_static_demo_tokens_still_work():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/v1/me", headers={"Authorization": "Bearer token-a"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "demo-a@arbor.eval"
