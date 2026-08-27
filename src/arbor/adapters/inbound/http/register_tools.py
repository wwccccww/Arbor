from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arbor.adapters.inbound.http.schemas import TicketToolIn
from arbor.application.tools.run_tools import allowed_tool_names
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


@dataclass
class ToolsHttpDeps:
    personas: object
    ticket_tool: object
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
