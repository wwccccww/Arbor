from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from arbor.domain.persona.authorization import ToolPolicy
from arbor.domain.shared.ids import TenantId, UserId
from arbor.observability.helpers import obs_or_noop

_TOOL_ALIASES = {
    "calendar": "calendar",
    "日程": "calendar",
    "日历": "calendar",
    "ticket": "ticket",
    "工单": "ticket",
    "报修": "ticket",
    "order": "order",
    "订单": "order",
    "查单": "order",
    "yunhui.order.query": "order",
    "recommend": "recommend",
    "推荐": "recommend",
    "yunhui.product.recommend": "recommend",
    "aftersale": "aftersale",
    "售后": "aftersale",
    "yunhui.aftersale.create": "aftersale",
}

_TOOL_TRIGGERS: dict[str, re.Pattern[str]] = {
    "calendar": re.compile(r"日程|日历|会议|约会|几点|什么时候|安排", re.IGNORECASE),
    "ticket": re.compile(r"工单|报修|故障|维修|投诉|ticket", re.IGNORECASE),
    "order": re.compile(r"订单|查单|物流|快递|单号|发货", re.IGNORECASE),
    "recommend": re.compile(r"推荐|买什么|有什么货|货品|商品", re.IGNORECASE),
    "aftersale": re.compile(r"售后|退货|退款|换货|退换", re.IGNORECASE),
}

_ORDER_ID = re.compile(r"\b([A-Za-z]{1,8}\d{6,})\b")


def extract_order_id(text: str) -> str:
    match = _ORDER_ID.search(text or "")
    return match.group(1) if match else ""


def aftersale_kind(text: str) -> str:
    blob = text or ""
    if "退款" in blob:
        return "refund"
    if "换货" in blob:
        return "exchange"
    return "return"


def normalize_tool_name(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if not key:
        return None
    return _TOOL_ALIASES.get(key) or (key if key in _TOOL_TRIGGERS else None)


def _stub_ticket_result(text: str) -> dict:
    title = (text or "").strip()[:80] or "用户反馈"
    return {
        "tool": "ticket",
        "status": "ok",
        "provider": "stub",
        "ticket_id": "stub-ticket-001",
        "title": title,
        "note": "演示工单已登记（stub），未连接真实工单系统",
    }


def _stub_calendar_result() -> dict:
    now = datetime.now(UTC)
    return {
        "tool": "calendar",
        "status": "ok",
        "provider": "stub",
        "summary": "演示日程（stub）",
        "events": [
            {
                "title": "与用户视频通话",
                "start": now.replace(hour=20, minute=0, second=0, microsecond=0).isoformat(),
                "note": "本地 stub，未连接真实日历 API",
            }
        ],
    }


def allowed_tool_names(tool_policy: ToolPolicy | None) -> set[str]:
    if tool_policy is None:
        return set()
    allowed: set[str] = set()
    for raw in tool_policy.allowed_tools or []:
        text = str(raw).strip()
        if not text:
            continue
        allowed.add(text)
        name = normalize_tool_name(text)
        if name:
            allowed.add(name)
    return allowed


def run_persona_tools(
    text: str,
    tool_policy: ToolPolicy | None,
    *,
    tenant_id: TenantId | None = None,
    user_id: UserId | None = None,
    calendar_tool: object | None = None,
    ticket_tool: object | None = None,
    mall_tool: object | None = None,
    observability: object | None = None,
) -> list[dict]:
    """Run allowed tools when user text matches keyword triggers."""
    obs = obs_or_noop(observability)
    allowed = allowed_tool_names(tool_policy)
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
        started = time.perf_counter()
        try:
            if name == "calendar":
                if calendar_tool is not None and tenant_id is not None and user_id is not None:
                    result = calendar_tool.list_upcoming(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        query_text=haystack,
                    )
                else:
                    result = _stub_calendar_result()
            elif name == "ticket":
                if ticket_tool is not None and tenant_id is not None and user_id is not None:
                    title = haystack[:80] or "用户反馈"
                    result = ticket_tool.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        title=title,
                        description=haystack,
                    )
                else:
                    result = _stub_ticket_result(haystack)
            elif name in {"order", "recommend", "aftersale"}:
                result = _run_mall_tool(
                    name,
                    haystack,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    mall_tool=mall_tool,
                )
            else:
                continue
            obs.event(
                "tool.call",
                tool=name,
                result="success",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            results.append(result)
        except Exception as exc:
            obs.event(
                "tool.call",
                tool=name,
                result="error",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error_kind=exc.__class__.__name__,
            )
            raise
    return results


def _run_mall_tool(
    name: str,
    text: str,
    *,
    tenant_id: TenantId | None,
    user_id: UserId | None,
    mall_tool: object | None,
) -> dict:
    from arbor.application.tools.yunhui_catalog import (
        demo_create_aftersale,
        demo_query_orders,
        demo_recommend_products,
    )

    order_id = extract_order_id(text)
    kind = aftersale_kind(text)
    if mall_tool is None or tenant_id is None or user_id is None:
        if name == "order":
            return demo_query_orders(query=text, order_id=order_id)
        if name == "recommend":
            return demo_recommend_products(query=text)
        return demo_create_aftersale(order_id=order_id, reason=text[:200], kind=kind)
    if name == "order":
        return mall_tool.query_orders(
            tenant_id=tenant_id,
            user_id=user_id,
            query=text,
            order_id=order_id,
        )
    if name == "recommend":
        return mall_tool.recommend_products(
            tenant_id=tenant_id,
            user_id=user_id,
            query=text,
        )
    return mall_tool.create_aftersale(
        tenant_id=tenant_id,
        user_id=user_id,
        order_id=order_id,
        reason=text[:200],
        kind=kind,
    )
