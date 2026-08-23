from __future__ import annotations

import json
import re

import httpx

from arbor.env import chat_api_key, chat_base_url, chat_model


class DeepSeekUnavailable(RuntimeError):
    pass


class DeepSeekChatLLM:
    """Chat completion adapter. Does not log the API key."""

    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self.last_injected: list[str] = []
        self.last_slots: dict | None = None

    def complete(self, *, prompt_slots: dict, text: str, injected_memory_ids: list[str]) -> dict:
        key = chat_api_key()
        if not key:
            raise DeepSeekUnavailable("DEEPSEEK_API_KEY missing")
        self.last_slots = prompt_slots
        self.last_injected = list(injected_memory_ids)
        payload = {
            "model": chat_model(),
            "messages": [
                {"role": "system", "content": _system_prompt(prompt_slots, injected_memory_ids)},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        response = httpx.post(
            f"{chat_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise DeepSeekUnavailable(f"deepseek HTTP {response.status_code}")
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_model_json(content)


def _system_prompt(prompt_slots: dict, injected_memory_ids: list[str]) -> str:
    profile = prompt_slots.get("profile") or {}
    name = profile.get("display_name") or "助手"
    return "\n".join(
        [
            f"你是 Arbor 人设「{name}」。只能根据下面注入的上下文回答。",
            "禁止使用上下文里没有的事实。不知道就说「我这边没有这条记录」。",
            "只输出 JSON：{\"text\": \"...\", \"citations\": [\"memory-id\", ...]}",
            "citations 只能来自下列 memory id，没有就输出空数组。",
            f"可用 memory id: {injected_memory_ids}",
            "档案: " + json.dumps(profile, ensure_ascii=False),
            "会话摘要: " + str(prompt_slots.get("thread_summary") or ""),
            "事件: " + json.dumps(prompt_slots.get("event_hits") or [], ensure_ascii=False),
            "记忆: " + json.dumps(prompt_slots.get("memory_hits") or [], ensure_ascii=False),
        ]
    )


def _parse_model_json(content: str) -> dict:
    blob = content.strip()
    match = re.search(r"\{.*\}", blob, flags=re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            text = str(data.get("text") or "")
            citations = [c for c in (data.get("citations") or []) if isinstance(c, str)]
            return {"text": text, "citations": citations}
        except json.JSONDecodeError:
            pass
    return {"text": blob, "citations": []}
