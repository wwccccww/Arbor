from __future__ import annotations

import time

from arbor.application.tools.run_tools import aftersale_kind, extract_order_id, normalize_tool_name
from arbor.domain.shared.ids import TenantId, UserId
from arbor.observability.helpers import obs_or_noop


def execute_tool_calls(
    calls: list[dict],
    *,
    allowed_tools: set[str],
    tenant_id: TenantId,
    user_id: UserId,
    query_text: str,
    calendar_tool: object | None = None,
    ticket_tool: object | None = None,
    mall_tool: object | None = None,
    observability: object | None = None,
) -> list[dict]:
    """Run tools requested by the LLM JSON envelope."""
    obs = obs_or_noop(observability)
    results: list[dict] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = normalize_tool_name(str(call.get("name") or ""))
        if not name or name not in allowed_tools:
            continue
        started = time.perf_counter()
        result_label = "success"
        try:
            if name == "calendar" and calendar_tool is not None:
                results.append(
                    calendar_tool.list_upcoming(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        query_text=query_text,
                    )
                )
            elif name == "ticket" and ticket_tool is not None:
                reason = str(call.get("reason") or call.get("title") or query_text).strip()
                title = reason[:80] or "用户反馈"
                results.append(
                    ticket_tool.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        title=title,
                        description=query_text,
                    )
                )
            elif name in {"order", "recommend", "aftersale"}:
                results.append(
                    _invoke_mall(
                        name,
                        call,
                        query_text=query_text,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        mall_tool=mall_tool,
                    )
                )
        except Exception as exc:
            result_label = "error"
            obs.event(
                "tool.call",
                tool=name,
                result=result_label,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error_kind=exc.__class__.__name__,
            )
            raise
        else:
            obs.event(
                "tool.call",
                tool=name,
                result=result_label,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
    return results


def _invoke_mall(
    name: str,
    call: dict,
    *,
    query_text: str,
    tenant_id: TenantId,
    user_id: UserId,
    mall_tool: object | None,
) -> dict:
    from arbor.application.tools.yunhui_catalog import (
        demo_create_aftersale,
        demo_query_orders,
        demo_recommend_products,
    )

    blob = " ".join(
        str(call.get(key) or "")
        for key in ("reason", "query", "order_id", "title")
    )
    blob = f"{blob} {query_text}".strip()
    order_id = str(call.get("order_id") or "").strip() or extract_order_id(blob)
    query = str(call.get("query") or call.get("reason") or query_text)
    kind = str(call.get("kind") or "").strip() or aftersale_kind(blob)
    if mall_tool is None:
        if name == "order":
            return demo_query_orders(query=query, order_id=order_id)
        if name == "recommend":
            return demo_recommend_products(query=query)
        return demo_create_aftersale(order_id=order_id, reason=query[:200], kind=kind)
    if name == "order":
        return mall_tool.query_orders(
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
            order_id=order_id,
        )
    if name == "recommend":
        return mall_tool.recommend_products(
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
        )
    return mall_tool.create_aftersale(
        tenant_id=tenant_id,
        user_id=user_id,
        order_id=order_id,
        reason=query[:200],
        kind=kind,
    )
