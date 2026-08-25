from fastapi.testclient import TestClient

from apps.api.main import create_app, create_app_from_env
from arbor.adapters.outbound.deepseek import DeepSeekChatLLM, DeepSeekReasoner, DeepSeekUnavailable
from arbor.adapters.outbound.inmemory import ScriptedLLM, ScriptedReasoner


def test_create_app_stays_scripted_even_if_key_present(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-should-not-be-used")
    app = create_app()
    assert isinstance(app.state.send.llm, ScriptedLLM)
    assert isinstance(app.state.send.reasoner, ScriptedReasoner)


def test_create_app_from_env_uses_scripted_without_key(monkeypatch):
    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "")
    monkeypatch.setattr("arbor.env.database_url", lambda: "")
    monkeypatch.setattr("apps.api.factory.embedding_client_from_env", lambda: None)
    app = create_app_from_env()
    assert isinstance(app.state.send.llm, ScriptedLLM)
    assert isinstance(app.state.send.reasoner, ScriptedReasoner)


def test_create_app_from_env_uses_deepseek_when_key_present(monkeypatch):
    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "sk-test")
    monkeypatch.setattr("arbor.env.database_url", lambda: "")
    monkeypatch.setattr("apps.api.factory.embedding_client_from_env", lambda: None)
    app = create_app_from_env()
    assert isinstance(app.state.send.llm, DeepSeekChatLLM)
    assert isinstance(app.state.send.reasoner, DeepSeekReasoner)


def test_me_runtime_defaults_to_scripted_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/v1/me", headers={"Authorization": "Bearer token-a"})
    assert r.status_code == 200
    assert r.json()["runtime"] == {"llm": "scripted", "store": "memory", "embed": "fixture"}


def test_me_runtime_reports_deepseek(monkeypatch):
    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "sk-test")
    monkeypatch.setattr("arbor.env.database_url", lambda: "")
    monkeypatch.setattr("apps.api.factory.embedding_client_from_env", lambda: None)
    client = TestClient(create_app_from_env(), raise_server_exceptions=False)
    r = client.get("/v1/me", headers={"Authorization": "Bearer token-a"})
    assert r.json()["runtime"] == {"llm": "deepseek", "store": "memory", "embed": "fixture"}


def test_create_app_from_env_falls_back_when_postgres_down(monkeypatch):
    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "")
    monkeypatch.setattr("apps.api.factory.embedding_client_from_env", lambda: None)
    monkeypatch.setattr(
        "arbor.env.database_url",
        lambda: "postgresql://arbor:arbor@127.0.0.1:59999/arbor",
    )
    app = create_app_from_env()
    assert app.state.runtime["store"] == "memory"
    assert isinstance(app.state.send.llm, ScriptedLLM)


def test_chat_maps_deepseek_unavailable():
    class BoomLLM:
        def complete(self, **_kwargs):
            raise DeepSeekUnavailable("deepseek HTTP 503")

    client = TestClient(create_app(llm=BoomLLM()), raise_server_exceptions=False)
    r = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers={
            "Authorization": "Bearer token-a",
            "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
        },
        json={"text": "还在吗"},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
