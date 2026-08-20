from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.rate_limit import InMemoryRateLimiter
from arbor.domain.errors import DomainError


def test_same_token_second_request_is_rate_limited():
    client = TestClient(
        create_app(rate_limit_per_window=1, rate_window_seconds=60),
        raise_server_exceptions=False,
    )
    headers = {"Authorization": "Bearer token-a"}
    first = client.get("/v1/me", headers=headers)
    assert first.status_code == 200
    second = client.get("/v1/me", headers=headers)
    assert second.status_code == 429
    err = second.json()["error"]
    assert err["code"] == "RATE_LIMITED"
    assert len(err["request_id"]) == 26
    assert set(err["request_id"]) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_other_token_has_its_own_quota():
    client = TestClient(
        create_app(rate_limit_per_window=1, rate_window_seconds=60),
        raise_server_exceptions=False,
    )
    owner = {"Authorization": "Bearer token-a"}
    member = {"Authorization": "Bearer token-member"}
    assert client.get("/v1/me", headers=owner).status_code == 200
    assert client.get("/v1/me", headers=owner).status_code == 429
    assert client.get("/v1/me", headers=member).status_code == 200


def test_anonymous_requests_share_anon_quota():
    client = TestClient(
        create_app(rate_limit_per_window=1, rate_window_seconds=60),
        raise_server_exceptions=False,
    )
    first = client.get("/v1/me")
    assert first.status_code == 401
    second = client.get("/v1/me")
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"


def test_docs_and_openapi_are_not_rate_limited():
    client = TestClient(
        create_app(rate_limit_per_window=1, rate_window_seconds=60),
        raise_server_exceptions=False,
    )
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/v1/me", headers={"Authorization": "Bearer token-a"}).status_code == 200


def test_window_expiry_allows_another_request():
    now = [0.0]
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    limiter.check("token-a")
    try:
        limiter.check("token-a")
        raise AssertionError("expected RATE_LIMITED")
    except DomainError as exc:
        assert exc.code == "RATE_LIMITED"
    now[0] = 61.0
    limiter.check("token-a")
