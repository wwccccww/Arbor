from __future__ import annotations

import httpx

from arbor.env import embedding_api_key, embedding_base_url, embedding_model


class EmbeddingUnavailable(RuntimeError):
    pass


class HttpEmbeddingClient:
    """OpenAI-compatible embeddings adapter. Default path is bge-m3 via SiliconFlow."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.model = embedding_model()
        self.label = "bge-m3" if "bge" in self.model.lower() else self.model

    def embed(self, text: str) -> list[float]:
        if text is None:
            raise EmbeddingUnavailable("text required")
        key = embedding_api_key()
        if not key:
            raise EmbeddingUnavailable("EMBEDDING_API_KEY missing")
        response = httpx.post(
            f"{embedding_base_url()}/embeddings",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": text, "encoding_format": "float"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise EmbeddingUnavailable(f"embedding HTTP {response.status_code}")
        try:
            vector = response.json()["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingUnavailable("embedding response missing vector") from exc
        return [float(item) for item in vector]


def embedding_client_from_env() -> HttpEmbeddingClient | None:
    if not embedding_api_key():
        return None
    return HttpEmbeddingClient()
