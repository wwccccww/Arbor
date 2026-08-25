from arbor.adapters.outbound.embedding import HttpEmbeddingClient, embedding_client_from_env


def test_embedding_client_from_env_none_without_key(monkeypatch):
    monkeypatch.setattr("arbor.adapters.outbound.embedding.embedding_api_key", lambda: "")
    assert embedding_client_from_env() is None


def test_http_embedding_parses_openai_response(monkeypatch):
    monkeypatch.setattr("arbor.adapters.outbound.embedding.embedding_api_key", lambda: "sk-emb")
    monkeypatch.setattr(
        "arbor.adapters.outbound.embedding.embedding_base_url",
        lambda: "https://api.siliconflow.cn/v1",
    )
    monkeypatch.setattr("arbor.adapters.outbound.embedding.embedding_model", lambda: "BAAI/bge-m3")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    def fake_post(url, **kwargs):
        assert url.endswith("/embeddings")
        assert kwargs["json"]["model"] == "BAAI/bge-m3"
        assert kwargs["json"]["input"] == "林夏讨厌香菜"
        return FakeResponse()

    monkeypatch.setattr("arbor.adapters.outbound.embedding.httpx.post", fake_post)
    client = HttpEmbeddingClient()
    assert client.label == "bge-m3"
    assert client.embed("林夏讨厌香菜") == [0.1, 0.2, 0.3]


def test_create_app_from_env_uses_http_embed(monkeypatch):
    from apps.api.main import create_app_from_env

    monkeypatch.setattr("arbor.env.chat_api_key", lambda: "")
    monkeypatch.setattr("arbor.env.database_url", lambda: "")
    monkeypatch.setattr("arbor.env.embedding_api_key", lambda: "sk-emb")
    monkeypatch.setattr("arbor.env.embedding_model", lambda: "BAAI/bge-m3")

    class StubEmbed:
        label = "bge-m3"

        def embed(self, text: str) -> list[float]:
            return [float(len(text or "")), 1.0, 0.0]

    monkeypatch.setattr(
        "apps.api.factory.embedding_client_from_env",
        lambda: StubEmbed(),
    )
    app = create_app_from_env()
    assert app.state.runtime["embed"] == "bge-m3"
    assert app.state.send.embed.embed("hi")[0] == 2.0
