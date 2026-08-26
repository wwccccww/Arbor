from __future__ import annotations

import json

import httpx

from arbor.domain.conversation.stream import StreamFinished, extract_text_delta, parse_model_out
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
        return parse_model_out(content)

    def complete_stream(self, *, prompt_slots: dict, text: str, injected_memory_ids: list[str]):
        """Stream the ``text`` portion of the model reply, token by token.

        The model is instructed to emit a JSON envelope; the streamed deltas are
        that envelope. We extract only the human-readable ``text`` field and
        yield it incrementally, so the UI can typewriter-render it. After the
        stream closes we yield a :class:`StreamFinished` sentinel carrying the
        raw envelope, so the caller can parse ``citations`` reliably.
        """
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
            "stream": True,
        }
        buffer = ""
        emitted = 0
        with httpx.stream(
            "POST",
            f"{chat_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        ) as response:
            if response.status_code >= 400:
                raise DeepSeekUnavailable(f"deepseek HTTP {response.status_code}")
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if not delta:
                    continue
                buffer += delta
                current = extract_text_delta(buffer)
                if len(current) > emitted:
                    yield current[emitted:]
                    emitted = len(current)
        yield StreamFinished(buffer)


def _system_prompt(prompt_slots: dict, injected_memory_ids: list[str]) -> str:
    profile = prompt_slots.get("profile") or {}
    name = profile.get("display_name") or "助手"
    lines = [
        f"你是 Arbor 人设「{name}」。只能根据下面注入的上下文回答。",
        "禁止使用上下文里没有的事实。不知道就说「我这边没有这条记录」。",
        "只输出 JSON：{\"text\": \"...\", \"citations\": [\"memory-id\", ...]"
        + (
            ", \"tool_calls\": [{\"name\": \"calendar\"|\"ticket\", \"reason\": \"...\"}]"
            if prompt_slots.get("llm_tool_calls_enabled")
            else ""
        )
        + "}",
        "citations 只能来自下列 memory id，没有就输出空数组。",
        f"可用 memory id: {injected_memory_ids}",
    ]
    if prompt_slots.get("llm_tool_calls_enabled"):
        allowed = prompt_slots.get("allowed_tool_names") or []
        lines.append(
            "若需查日程或登记工单且 tool_results 不足，在 tool_calls 中声明；否则 tool_calls 留空数组。"
        )
        lines.append(f"可调工具: {json.dumps(allowed, ensure_ascii=False)}")
    lines.extend(
        [
            "档案: " + json.dumps(profile, ensure_ascii=False),
            "会话摘要: " + str(prompt_slots.get("thread_summary") or ""),
            "事件: " + json.dumps(prompt_slots.get("event_hits") or [], ensure_ascii=False),
            "记忆: " + json.dumps(prompt_slots.get("memory_hits") or [], ensure_ascii=False),
            "工具权限: " + json.dumps(prompt_slots.get("tool_policy") or {}, ensure_ascii=False),
            "工具调用结果: " + json.dumps(prompt_slots.get("tool_results") or [], ensure_ascii=False),
        ]
    )
    return "\n".join(lines)
