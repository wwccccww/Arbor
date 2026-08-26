from __future__ import annotations

import json
import re

import httpx

from arbor.env import chat_api_key, chat_base_url, reasoner_model

ALLOWED_KINDS = frozenset({"fact", "event", "conflict", "emotion"})


class DeepSeekReasoner:
    """Extract durable facts into Inbox. Failures return None so chat still works."""

    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self.last_text: str | None = None

    def extract(self, text: str) -> dict | None:
        self.last_text = text
        if not (text or "").strip():
            return None
        key = chat_api_key()
        if not key:
            return None
        model = reasoner_model()
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": _extract_prompt()},
                {"role": "user", "content": text},
            ],
            "max_tokens": 800,
        }
        if "reasoner" not in model:
            payload["temperature"] = 0.2
        try:
            response = httpx.post(
                f"{chat_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        parsed = parse_extract(content)
        if parsed is None:
            return None
        parsed.setdefault("source_text", text)
        return parsed

    def summarize(self, dialogue: str, prior: str = "") -> str | None:
        blob = (dialogue or "").strip()
        if not blob:
            return None
        key = chat_api_key()
        if not key:
            return None
        model = reasoner_model()
        system = (
            "你是会话摘要器。把最近对话压缩成 2-4 句中文摘要，保留事实、约定与情绪转折。"
            "不要编造。若与旧摘要冲突，以最新对话为准。"
        )
        user_parts = []
        if (prior or "").strip():
            user_parts.append(f"旧摘要：{prior.strip()}")
        user_parts.append(f"最近对话：\n{blob}")
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            "max_tokens": 300,
        }
        if "reasoner" not in model:
            payload["temperature"] = 0.2
        try:
            response = httpx.post(
                f"{chat_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            return str(response.json()["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, ValueError):
            return None


def _extract_prompt() -> str:
    return '你是 Arbor 的记忆抽取器。只根据用户这句话判断有没有应写入人设记忆的稳定事实或事件。\n寒暄、提问、情绪、一次性指令不要抽取。\n只输出 JSON，不要其它文字。\n有可记内容：{"kind": "fact、event、conflict 或 emotion", "text": "第三人称短句", "skip": false}\n没有：{"skip": true, "kind": null, "text": ""}\n不要编造。text 必须能从原句推出。'


def parse_extract(content: str) -> dict | None:
    blob = (content or "").strip()
    if not blob:
        return None
    match = re.search(r"\{.*\}", blob, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if data.get("skip") is True:
        return None
    text = str(data.get("text") or "").strip()
    if not text:
        return None
    kind = data.get("kind") or "fact"
    if kind not in ALLOWED_KINDS:
        kind = "fact"
    return {"kind": kind, "text": text, "source_text": str(data.get("source_text") or "")}
