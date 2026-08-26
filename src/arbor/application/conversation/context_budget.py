from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    """Rough token count without external tokenizer (mixed CJK/Latin)."""
    if not text:
        return 0
    return max(1, (len(text) + 1) // 3)


def estimate_json_tokens(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return estimate_tokens(value)
    try:
        return estimate_tokens(json.dumps(value, ensure_ascii=False))
    except TypeError:
        return estimate_tokens(str(value))


def estimate_prompt_slots_tokens(prompt_slots: dict) -> int:
    total = 0
    for key in (
        "profile",
        "tool_policy",
        "thread_summary",
        "recent_turns",
        "event_hits",
        "memory_hits",
        "tool_results",
        "allowed_tool_names",
    ):
        total += estimate_json_tokens(prompt_slots.get(key))
    if prompt_slots.get("llm_tool_calls_enabled"):
        total += 40
    return total


def truncate_text(text: str, max_chars: int) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= max_chars:
        return stripped
    if max_chars <= 1:
        return "…"
    return stripped[: max_chars - 1].rstrip() + "…"


def trim_recent_turn(turn: dict, max_chars: int) -> dict:
    content = truncate_text(str(turn.get("content") or ""), max_chars)
    return {"role": turn.get("role") or "user", "content": content}

