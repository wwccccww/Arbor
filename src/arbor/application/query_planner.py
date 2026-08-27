from __future__ import annotations

import re

_SPLIT_MARKERS = (
    "因为",
    "所以",
    "如果",
    "那么",
    "后来",
    "上次",
    "之后",
    "之前",
    "并且",
    "同时",
)

_PROFILE_HINTS = ("住", "禁忌", "讨厌", "喜欢", "是谁", "叫什么", "哪里人", "职业")
_EPISODE_HINTS = ("上次", "那天", "什么时候", "哪次", "后来", "之前", "吵架", "面店")


def plan_queries(query: str, mode: str) -> list[dict]:
    stripped = (query or "").strip()
    if not stripped or mode == "off":
        return [{"query": stripped, "intent": "general"}]
    if mode != "rules":
        return [{"query": stripped, "intent": "general"}]

    parts: list[str] = [stripped]
    for marker in _SPLIT_MARKERS:
        next_parts: list[str] = []
        for part in parts:
            if marker in part and len(part) > len(marker) + 2:
                segments = re.split(re.escape(marker), part, maxsplit=1)
                for segment in segments:
                    piece = segment.strip()
                    if piece:
                        next_parts.append(piece)
            else:
                next_parts.append(part)
        parts = next_parts
        if len(parts) >= 3:
            break

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = part.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    if len(deduped) <= 1:
        return [{"query": stripped, "intent": _intent_for(stripped)}]

    planned: list[dict] = []
    for piece in deduped[:3]:
        planned.append({"query": piece, "intent": _intent_for(piece)})
    return planned


def _intent_for(text: str) -> str:
    if any(hint in text for hint in _PROFILE_HINTS):
        return "profile"
    if any(hint in text for hint in _EPISODE_HINTS):
        return "episode"
    return "general"
