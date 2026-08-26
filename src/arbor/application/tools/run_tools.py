from __future__ import annotations

import re
from datetime import datetime, timezone

from arbor.domain.persona.authorization import ToolPolicy

_TOOL_ALIASES = {
    "calendar": "calendar",
    "日程": "calendar",
    "日历": "calendar",
    "ticket": "ticket",
    "工单": "ticket",
    "报修": "ticket",
}

_TOOL_TRIGGERS: dict[str, re.Pattern[str]] = {
    "calendar": re.compile(r"日程|日历|会议|约会|几点|什么时候|安排", re.I),
    "ticket": re.compile(r"工单|报修|故障|维修|投诉|ticket", re.I),
}


def _normalize_tool_name(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if not key:
        return None
    return _TOOL_ALIASES.get(key) or (key if key in _TOOL_TRIGGERS else None)


def _stub_calendar_result() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "tool": "calendar",
        "status": "ok",
        "summary": "演示日程（stub）",
        "events": [
            {
                "title": "与用户视频通话",
                "start": now.replace(hour=20, minute=0, second=0, microsecond=0).isoformat(),
                "note": "本地 stub，未连接真实日历 API",
            }
        ],
    }


def _stub_ticket_result(text: str) -> dict:
    title = (text or "").strip()[:80] or "用户反馈"
    return {
        "tool": "ticket",
        "status": "ok",
        "ticket_id": "stub-ticket-001",
        "title": title,
        "note": "演示工单已登记（stub），未连接真实工单系统",
    }


def run_persona_tools(text: str, tool_policy: ToolPolicy | None) -> list[dict]:
    """Run allowed stub tools when user text matches triggers."""
    if tool_policy is None:
        return []
    allowed: set[str] = set()
    for raw in tool_policy.allowed_tools:
        name = _normalize_tool_name(str(raw))
        if name:
            allowed.add(name)
    if not allowed:
        return []
    haystack = (text or "").strip()
    if not haystack:
        return []
    results: list[dict] = []
    for name in sorted(allowed):
        pattern = _TOOL_TRIGGERS.get(name)
        if pattern is None or not pattern.search(haystack):
            continue
        if name == "calendar":
            results.append(_stub_calendar_result())
        elif name == "ticket":
            results.append(_stub_ticket_result(haystack))
    return results
