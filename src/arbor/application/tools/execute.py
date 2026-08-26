from __future__ import annotations

from arbor.application.tools.run_tools import normalize_tool_name
from arbor.domain.shared.ids import TenantId, UserId


def execute_tool_calls(
    calls: list[dict],
    *,
    allowed_tools: set[str],
    tenant_id: TenantId,
    user_id: UserId,
    query_text: str,
    calendar_tool: object | None = None,
    ticket_tool: object | None = None,
) -> list[dict]:
    """Run tools requested by the LLM JSON envelope."""
    results: list[dict] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = normalize_tool_name(str(call.get("name") or ""))
        if not name or name not in allowed_tools:
            continue
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
    return results
