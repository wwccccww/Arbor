from __future__ import annotations

import httpx

from arbor.env import embedding_api_key, embedding_base_url, embedding_model


class EmbeddingUnavailable(RuntimeError):
    pass


class HttpEmbeddingClient:
    """OpenAI-compatible embeddings adapter. Default path is bge-m3 via SiliconFlow."""

    # bge-m3 allows 8192 tokens; keep a conservative char cap for mixed CJK/Latin.
    max_input_chars = 12_000

    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self.model = embedding_model()
        self.label = "bge-m3" if "bge" in self.model.lower() else self.model

    def _prepare_text(self, text: str) -> str:
        blob = (text or "").strip()
        if not blob:
            return " "
        if len(blob) > self.max_input_chars:
            return blob[: self.max_input_chars]
        return blob

    def embed(self, text: str) -> list[float]:
        if text is None:
            raise EmbeddingUnavailable("text required")
        key = embedding_api_key()
        if not key:
            raise EmbeddingUnavailable("EMBEDDING_API_KEY missing")
        payload_text = self._prepare_text(text)
        last_error = "embedding request failed"
        for attempt in range(4):
            try:
                response = httpx.post(
                    f"{embedding_base_url()}/embeddings",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": payload_text, "encoding_format": "float"},
                    timeout=httpx.Timeout(self.timeout, connect=20.0),
                )
            except httpx.TimeoutException as exc:
                last_error = str(exc)
                if attempt >= 3:
                    raise EmbeddingUnavailable(last_error) from exc
                import time

                time.sleep(2**attempt)
                continue
            if response.status_code < 400:
                break
            last_error = f"embedding HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in {429, 500, 502, 503, 504} or attempt >= 3:
                raise EmbeddingUnavailable(last_error)
            import time

            time.sleep(2**attempt)
        else:
            raise EmbeddingUnavailable(last_error)
        try:
            vector = response.json()["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingUnavailable("embedding response missing vector") from exc
        return [float(item) for item in vector]


def embedding_client_from_env() -> HttpEmbeddingClient | None:
    if not embedding_api_key():
        return None
    return HttpEmbeddingClient()
