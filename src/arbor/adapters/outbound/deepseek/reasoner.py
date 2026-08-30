from __future__ import annotations

import json
import re
import time

import httpx

from arbor.domain.memory.memory import MemoryItem
from arbor.env import chat_api_key, chat_base_url, reasoner_model
from arbor.observability.helpers import http_status_class
from arbor.observability.llm import observed_llm_call, record_llm_usage

ALLOWED_KINDS = frozenset({"fact", "event", "conflict", "emotion"})


class DeepSeekReasoner:
    """Extract durable facts into Inbox. Failures return None so chat still works."""

    def __init__(self, *, timeout: float = 60.0, observability: object | None = None) -> None:
        self.timeout = timeout
        self.observability = observability
        self.last_text: str | None = None
        self.observability_model = reasoner_model()
        self.last_reasoning_content: str | None = None

    def extract(self, text: str, active_memories: list | None = None) -> dict | None:
        self.last_text = text
        if not (text or "").strip():
            return None
        key = chat_api_key()
        if not key:
            return None
        model = self.observability_model
        user_content = _format_extract_user(text, active_memories)
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": _extract_prompt(bool(active_memories))},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 800,
        }
        if "reasoner" not in model:
            payload["temperature"] = 0.2
        started = time.perf_counter()
        try:
            with observed_llm_call(self.observability, operation="extract", model=model):
                response = httpx.post(
                    f"{chat_base_url()}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=self.timeout,
                )
        except httpx.HTTPError:
            return None
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if response.status_code >= 400:
            if self.observability is not None:
                from arbor.observability.helpers import obs_or_noop

                obs_or_noop(self.observability).increment(
                    "arbor_llm_upstream_errors_total",
                    operation="extract",
                    status_class=http_status_class(response.status_code),
                )
            return None
        try:
            body = response.json()
            message = body["choices"][0]["message"]
            content = message["content"]
            reasoning = message.get("reasoning_content")
            self.last_reasoning_content = str(reasoning) if reasoning else None
            usage = body.get("usage") or {}
            record_llm_usage(
                self.observability,
                operation="extract",
                model=model,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        parsed = parse_extract(content)
        if parsed is None:
            if self.observability is not None:
                from arbor.observability.helpers import obs_or_noop

                obs_or_noop(self.observability).event(
                    "llm.extract",
                    model=model,
                    duration_ms=duration_ms,
                    result="skipped",
                )
            return None
        parsed.setdefault("source_text", text)
        if self.observability is not None:
            from arbor.observability.helpers import obs_or_noop

            obs_or_noop(self.observability).event(
                "llm.extract",
                model=model,
                duration_ms=duration_ms,
                result_kind=parsed.get("kind"),
                result="parsed",
            )
            obs_or_noop(self.observability).increment(
                "arbor_llm_requests_total",
                operation="extract",
                model=model,
                result="success",
            )
        return parsed

    def summarize(self, dialogue: str, prior: str = "") -> str | None:
        blob = (dialogue or "").strip()
        if not blob:
            return None
        key = chat_api_key()
        if not key:
            return None
        model = self.observability_model
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
        started = time.perf_counter()
        try:
            with observed_llm_call(self.observability, operation="summarize", model=model):
                response = httpx.post(
                    f"{chat_base_url()}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=self.timeout,
                )
        except httpx.HTTPError:
            return None
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if response.status_code >= 400:
            return None
        try:
            body = response.json()
            content = str(body["choices"][0]["message"]["content"]).strip()
            usage = body.get("usage") or {}
            record_llm_usage(
                self.observability,
                operation="summarize",
                model=model,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            if self.observability is not None:
                from arbor.observability.helpers import obs_or_noop

                obs_or_noop(self.observability).event(
                    "llm.summarize",
                    model=model,
                    duration_ms=duration_ms,
                    result="success",
                )
                obs_or_noop(self.observability).increment(
                    "arbor_llm_requests_total",
                    operation="summarize",
                    model=model,
                    result="success",
                )
            return content
        except (KeyError, IndexError, TypeError, ValueError):
            return None


def _format_extract_user(text: str, active_memories: list | None) -> str:
    if not active_memories:
        return text
    lines: list[str] = []
    for item in active_memories[:16]:
        if isinstance(item, MemoryItem):
            lines.append(f"- {item.id.value}: {item.text}")
        elif isinstance(item, dict):
            lines.append(f"- {item.get('id')}: {item.get('text')}")
    if not lines:
        return text
    return "已有 active 记忆：\n" + "\n".join(lines) + f"\n\n用户新句：{text}"


def _extract_prompt(with_memories: bool) -> str:
    base = (
        "你是 Arbor 的记忆抽取器。只根据用户这句话判断有没有应写入人设记忆的稳定事实或事件。\n"
        "寒暄、提问、情绪、一次性指令不要抽取。\n"
        "只输出 JSON，不要其它文字。\n"
        "有可记内容：{\"kind\": \"fact、event、conflict 或 emotion\", \"text\": \"第三人称短句\", \"skip\": false}\n"
        "没有：{\"skip\": true, \"kind\": null, \"text\": \"\"}\n"
        "不要编造。text 必须能从原句推出。"
    )
    if with_memories:
        base += (
            "\n若新句与已有记忆矛盾，kind 用 conflict，并填 conflicts_with 为已有记忆的 id（UUID）。"
            "示例：{\"kind\": \"conflict\", \"text\": \"…\", \"conflicts_with\": \"uuid\", \"skip\": false}"
        )
    return base


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
    if kind == "emotion":
        kind = "fact"
    memory_type = "episode_summary" if kind in {"event", "conflict"} else "fact"
    out: dict = {
        "kind": kind,
        "text": text,
        "source_text": str(data.get("source_text") or ""),
        "memory_type": memory_type,
    }
    conflict_raw = data.get("conflicts_with")
    if conflict_raw:
        out["conflicts_with"] = str(conflict_raw)
    return out
