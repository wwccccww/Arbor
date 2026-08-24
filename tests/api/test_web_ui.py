from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_root_explains_missing_web_build(tmp_path, monkeypatch):
    monkeypatch.setattr("apps.api.main.repo_root", lambda: tmp_path)
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/")
    assert r.status_code == 503
    assert "run.ps1" in r.text
    assert "npm run build" in r.text


def test_root_serves_built_index(tmp_path, monkeypatch):
    dist = tmp_path / "apps" / "web" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Arbor</title>", encoding="utf-8")
    monkeypatch.setattr("apps.api.main.repo_root", lambda: tmp_path)
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/")
    assert r.status_code == 200
    assert "Arbor" in r.text
