from __future__ import annotations

import base64

import httpx

from arbor.adapters.outbound.multimodal.types import MediaChunk, MediaParseResult
from arbor.env import chat_api_key, chat_base_url


class DeepSeekVisionDescriber:
    """Describe image bytes via chat-completions with image_url (OpenAI-compatible)."""

    def __init__(self, *, timeout: float = 90.0) -> None:
        self.timeout = timeout

    def describe(self, data: bytes, filename: str) -> MediaParseResult:
        key = chat_api_key()
        if not key or not data:
            return MediaParseResult(chunks=[], parser="vision", media_kind="image")
        lower = (filename or "").lower()
        mime = "image/jpeg"
        if lower.endswith(".png"):
            mime = "image/png"
        elif lower.endswith(".gif"):
            mime = "image/gif"
        elif lower.endswith(".webp"):
            mime = "image/webp"
        b64 = base64.b64encode(data).decode("ascii")
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "用中文简要描述这张图片中的场景、人物与文字（如有）。"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
            "max_tokens": 512,
        }
        response = httpx.post(
            f"{chat_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            return MediaParseResult(chunks=[], parser="vision", media_kind="image")
        text = (response.json()["choices"][0]["message"]["content"] or "").strip()
        if not text:
            return MediaParseResult(chunks=[], parser="vision", media_kind="image")
        chunk = MediaChunk(
            text=text,
            memory_type="image_caption",
            metadata={"source": filename, "parser": "deepseek-vision"},
        )
        return MediaParseResult(chunks=[chunk], parser="deepseek-vision", media_kind="image")


class StubVisionDescriber:
    def describe(self, data: bytes, filename: str) -> MediaParseResult:
        return MediaParseResult(chunks=[], parser="stub", media_kind="image")
