from fastapi.testclient import TestClient

from apps.api.main import create_app, create_app_from_env
from arbor.adapters.outbound.deepseek import DeepSeekChatLLM, DeepSeekUnavailable
from arbor.adapters.outbound.inmemory import ScriptedLLM


def test_create_app_stays_scripted_even_if_key_present(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-should-not-be-used")
    app = create_app()
    assert isinstance(app.state.send.llm, ScriptedLLM)


def test_create_app_from_env_uses_scripted_without_key(monkeypatch):
    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "")
    monkeypatch.setattr("arbor.env.database_url", lambda: "")
    app = create_app_from_env()
    assert isinstance(app.state.send.llm, ScriptedLLM)


def test_create_app_from_env_uses_deepseek_when_key_present(monkeypatch):
    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "sk-test")
    monkeypatch.setattr("arbor.env.database_url", lambda: "")
    app = create_app_from_env()
    assert isinstance(app.state.send.llm, DeepSeekChatLLM)


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
