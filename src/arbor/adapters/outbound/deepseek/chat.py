from __future__ import annotations

import json
import time

import httpx

from arbor.domain.conversation.stream import StreamFinished, extract_text_delta, parse_model_out
from arbor.env import chat_api_key, chat_base_url, chat_model
from arbor.observability.helpers import http_status_class
from arbor.observability.llm import observed_llm_call, record_llm_usage


class DeepSeekUnavailable(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class DeepSeekChatLLM:
    """Chat completion adapter. Does not log the API key."""

    def __init__(self, *, timeout: float = 60.0, observability: object | None = None) -> None:
        self.timeout = timeout
        self.observability = observability
        self.last_injected: list[str] = []
        self.last_slots: dict | None = None
        self.observability_model = chat_model()
        self.last_input_tokens: int | None = None
        self.last_output_tokens: int | None = None
        self.last_reasoning_content: str | None = None
        self.last_first_token_ms: float | None = None

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
        model = self.observability_model
        with observed_llm_call(self.observability, operation="chat", model=model, stream="false"):
            response = httpx.post(
                f"{chat_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                err = DeepSeekUnavailable(f"deepseek HTTP {response.status_code}", status_code=response.status_code)
                if self.observability is not None:
                    from arbor.observability.helpers import obs_or_noop

                    obs_or_noop(self.observability).increment(
                        "arbor_llm_upstream_errors_total",
                        operation="chat",
                        status_class=http_status_class(response.status_code),
                    )
                raise err
            body = response.json()
            message = body["choices"][0]["message"]
            content = message["content"]
            self._capture_usage(body, message)
            record_llm_usage(
                self.observability,
                operation="chat",
                model=model,
                input_tokens=self.last_input_tokens,
                output_tokens=self.last_output_tokens,
            )
            if self.observability is not None:
                from arbor.observability.helpers import obs_or_noop

                obs_or_noop(self.observability).increment(
                    "arbor_llm_requests_total",
                    operation="chat",
                    model=model,
                    result="success",
                )
        return parse_model_out(content)

    def complete_stream(self, *, prompt_slots: dict, text: str, injected_memory_ids: list[str]):
        """Stream the ``text`` portion of the model reply, token by token."""
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
        model = self.observability_model
        started = time.perf_counter()
        first_token_at: float | None = None
        with (
            observed_llm_call(self.observability, operation="chat", model=model, stream="true"),
            httpx.stream(
                "POST",
                f"{chat_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            ) as response,
        ):
                if response.status_code >= 400:
                    raise DeepSeekUnavailable(
                        f"deepseek HTTP {response.status_code}",
                        status_code=response.status_code,
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        usage = chunk.get("usage")
                        if usage:
                            self.last_input_tokens = usage.get("prompt_tokens")
                            self.last_output_tokens = usage.get("completion_tokens")
                    except (KeyError, IndexError, json.JSONDecodeError):
                        continue
                    if not delta:
                        continue
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        self.last_first_token_ms = round((first_token_at - started) * 1000, 2)
                    buffer += delta
                    current = extract_text_delta(buffer)
                    if len(current) > emitted:
                        yield current[emitted:]
                        emitted = len(current)
        record_llm_usage(
            self.observability,
            operation="chat",
            model=model,
            input_tokens=self.last_input_tokens,
            output_tokens=self.last_output_tokens,
            first_token_ms=self.last_first_token_ms,
        )
        if self.observability is not None:
            from arbor.observability.helpers import obs_or_noop

            obs_or_noop(self.observability).increment(
                "arbor_llm_requests_total",
                operation="chat",
                model=model,
                result="success",
            )
        yield StreamFinished(buffer)

    def _capture_usage(self, body: dict, message: dict) -> None:
        usage = body.get("usage") or {}
        self.last_input_tokens = usage.get("prompt_tokens")
        self.last_output_tokens = usage.get("completion_tokens")
        reasoning = message.get("reasoning_content")
        self.last_reasoning_content = str(reasoning) if reasoning else None


def _system_prompt(prompt_slots: dict, injected_memory_ids: list[str]) -> str:
    profile = prompt_slots.get("profile") or {}
    name = profile.get("display_name") or "助手"
    lines = [
        f"你是 Arbor 人设「{name}」。只能根据下面注入的上下文回答。",
        "禁止使用上下文里没有的事实。不知道就说「我这边没有这条记录」。",
    ]
    if prompt_slots.get("eval_generation_mode"):
        lines.extend(
            [
                "评测模式：只根据「记忆」「事件」作答；多跳问题先合并多条证据再给一句完整结论。",
                "回答尽量简洁；citations 必须列出实际用到的 memory id，没用到的不要列。",
            ]
        )
    lines.extend(
        [
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
    )
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
            "近期对话: " + json.dumps(prompt_slots.get("recent_turns") or [], ensure_ascii=False),
            "事件: " + json.dumps(prompt_slots.get("event_hits") or [], ensure_ascii=False),
            "记忆: " + json.dumps(prompt_slots.get("memory_hits") or [], ensure_ascii=False),
            "工具权限: " + json.dumps(prompt_slots.get("tool_policy") or {}, ensure_ascii=False),
            "工具调用结果: " + json.dumps(prompt_slots.get("tool_results") or [], ensure_ascii=False),
        ]
    )
    return "\n".join(lines)
