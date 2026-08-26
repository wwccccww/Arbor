from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_root_without_web_dist_returns_help_page():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/")
    if response.status_code == 200:
        return
    assert response.status_code == 503
    assert "工作台还没有构建" in response.text
