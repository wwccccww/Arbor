from __future__ import annotations

import json
import re

import httpx

from arbor.env import chat_api_key, chat_base_url, chat_model

_SPLIT_MARKERS = (
    "所以",
    "如果",
    "那么",
    "后来",
    "上次",
    "之后",
    "之前",
    "并且",
    "同时",
    "以及",
    "还有",
    " and ",
    " AND ",
)

_PROFILE_HINTS = ("住", "禁忌", "讨厌", "喜欢", "是谁", "叫什么", "哪里人", "职业")
_EPISODE_HINTS = ("上次", "那天", "什么时候", "哪次", "后来", "之前", "吵架", "面店")
_CAUSAL_HINTS = (
    "为什么",
    "为何",
    "怎么会",
    "什么原因",
    "有什么关系",
    "导致",
    "闹翻",
    "是因为",
    "除了",
    "定了什么",
    "定了哪些",
)


def plan_queries(query: str, mode: str) -> list[dict]:
    stripped = (query or "").strip()
    if not stripped or mode == "off":
        return [{"query": stripped, "intent": "general"}]
    if mode == "llm":
        planned = _llm_plan_queries(stripped)
        if planned:
            return planned
        return _rules_plan_queries(stripped)
    if mode != "rules":
        return [{"query": stripped, "intent": _intent_for(stripped)}]
    return _rules_plan_queries(stripped)


def _rules_plan_queries(stripped: str) -> list[dict]:
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


def _llm_plan_queries(query: str) -> list[dict] | None:
    key = chat_api_key()
    if not key:
        return None
    model = chat_model()
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _llm_plan_prompt()},
            {"role": "user", "content": query},
        ],
        "max_tokens": 400,
    }
    if "reasoner" not in model:
        payload["temperature"] = 0.1
    try:
        response = httpx.post(
            f"{chat_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return _parse_llm_plan(content, query)


def _llm_plan_prompt() -> str:
    return (
        "你是 Arbor 检索 query 规划器。把用户问题拆成最多 3 个子 query，用于从人设记忆里检索。"
        "只输出 JSON 数组，不要其它文字。"
        "元素格式：{\"query\": \"子问题\", \"intent\": \"profile|episode|general\"}。"
        "profile：档案/喜好/禁忌；episode：具体事件/时间线；causal：因果/为何/关系；general：其它。"
        "若无需拆分，返回单元素数组。不要编造用户没问的内容。"
    )


def _parse_llm_plan(content: str, fallback_query: str) -> list[dict] | None:
    blob = (content or "").strip()
    if not blob:
        return None
    match = re.search(r"\[.*\]", blob, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or not data:
        return None
    planned: list[dict] = []
    seen: set[str] = set()
    for item in data[:3]:
        if not isinstance(item, dict):
            continue
        piece = str(item.get("query") or "").strip()
        if not piece or piece in seen:
            continue
        seen.add(piece)
        intent = str(item.get("intent") or "general").strip().lower()
        if intent not in {"profile", "episode", "general", "causal"}:
            intent = _intent_for(piece)
        planned.append({"query": piece, "intent": intent})
    if not planned:
        return None
    return planned


def _intent_for(text: str) -> str:
    if any(hint in text for hint in _CAUSAL_HINTS):
        return "causal"
    if any(hint in text for hint in _PROFILE_HINTS):
        return "profile"
    if any(hint in text for hint in _EPISODE_HINTS):
        return "episode"
    return "general"
