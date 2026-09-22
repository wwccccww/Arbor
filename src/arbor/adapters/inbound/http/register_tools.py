from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arbor.adapters.inbound.http.schemas import (
    CalendarToolIn,
    TicketToolIn,
    YunhuiAftersaleIn,
    YunhuiOrderIn,
    YunhuiRecommendIn,
)
from arbor.application.tools.run_tools import aftersale_kind, allowed_tool_names, extract_order_id
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


@dataclass
class ToolsHttpDeps:
    personas: object
    ticket_tool: object
    calendar_tool: object
    mall_tool: object
    auth: AuthorizationPolicy
    current_user: Callable
    resolve_tenant: Callable | None = None


def register_tools_routes(app, deps: ToolsHttpDeps) -> None:
    from fastapi import Body, Header

    @app.post("/v1/personas/{persona_id}/tools/ticket")
    def post_ticket_tool(
        persona_id: str,
        payload: TicketToolIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if deps.resolve_tenant is not None:
            tenant = deps.resolve_tenant(user, x_tenant_id)
        else:
            tenant = TenantId(x_tenant_id or user.get("tenant_id") or "")
        persona = deps.personas.get(tenant, PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        if not deps.auth.can_chat(persona, UserId(user["user_id"])):
            raise DomainError("FORBIDDEN_CHAT", "chat grant required")
        allowed = allowed_tool_names(persona.tool_policy)
        if "ticket" not in allowed:
            raise DomainError("FORBIDDEN_TOOL", "ticket not allowed for persona")
        title = (payload.title or "").strip() or "用户反馈"
        description = (payload.description or "").strip() or title
        result = deps.ticket_tool.create(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            title=title[:120],
            description=description,
        )
        return result

    @app.post("/v1/personas/{persona_id}/tools/calendar")
    def post_calendar_tool(
        persona_id: str,
        payload: CalendarToolIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if deps.resolve_tenant is not None:
            tenant = deps.resolve_tenant(user, x_tenant_id)
        else:
            tenant = TenantId(x_tenant_id or user.get("tenant_id") or "")
        persona = deps.personas.get(tenant, PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        if not deps.auth.can_chat(persona, UserId(user["user_id"])):
            raise DomainError("FORBIDDEN_CHAT", "chat grant required")
        allowed = allowed_tool_names(persona.tool_policy)
        if "calendar" not in allowed:
            raise DomainError("FORBIDDEN_TOOL", "calendar not allowed for persona")
        query_text = (payload.query_text or "").strip() or "近期日程"
        return deps.calendar_tool.list_upcoming(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            query_text=query_text,
        )

    def _guard_mall(persona_id: str, authorization: str | None, x_tenant_id: str | None, tool_name: str):
        user = deps.current_user(authorization)
        if deps.resolve_tenant is not None:
            tenant = deps.resolve_tenant(user, x_tenant_id)
        else:
            tenant = TenantId(x_tenant_id or user.get("tenant_id") or "")
        persona = deps.personas.get(tenant, PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        if not deps.auth.can_chat(persona, UserId(user["user_id"])):
            raise DomainError("FORBIDDEN_CHAT", "chat grant required")
        allowed = allowed_tool_names(persona.tool_policy)
        if tool_name not in allowed:
            raise DomainError("FORBIDDEN_TOOL", f"{tool_name} not allowed for persona")
        return tenant, UserId(user["user_id"])

    @app.post("/v1/personas/{persona_id}/tools/yunhui/orders")
    def post_yunhui_orders(
        persona_id: str,
        payload: YunhuiOrderIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        tenant, user_id = _guard_mall(persona_id, authorization, x_tenant_id, "order")
        query = (payload.query or "").strip()
        order_id = (payload.order_id or "").strip() or extract_order_id(query)
        return deps.mall_tool.query_orders(
            tenant_id=tenant,
            user_id=user_id,
            query=query,
            order_id=order_id,
        )

    @app.post("/v1/personas/{persona_id}/tools/yunhui/recommend")
    def post_yunhui_recommend(
        persona_id: str,
        payload: YunhuiRecommendIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        tenant, user_id = _guard_mall(persona_id, authorization, x_tenant_id, "recommend")
        return deps.mall_tool.recommend_products(
            tenant_id=tenant,
            user_id=user_id,
            query=(payload.query or "").strip(),
            limit=max(1, min(int(payload.limit or 3), 5)),
        )

    @app.post("/v1/personas/{persona_id}/tools/yunhui/aftersales")
    def post_yunhui_aftersale(
        persona_id: str,
        payload: YunhuiAftersaleIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        tenant, user_id = _guard_mall(persona_id, authorization, x_tenant_id, "aftersale")
        reason = (payload.reason or "").strip()
        order_id = (payload.order_id or "").strip() or extract_order_id(reason)
        kind = (payload.kind or "").strip() or aftersale_kind(reason)
        return deps.mall_tool.create_aftersale(
            tenant_id=tenant,
            user_id=user_id,
            order_id=order_id,
            reason=reason,
            kind=kind,
        )
