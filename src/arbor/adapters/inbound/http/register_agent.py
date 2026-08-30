from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Body, Header

from arbor.adapters.inbound.http.schemas import AgentApprovalIn, AgentRunIn
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


@dataclass
class AgentHttpDeps:
    start_run: object
    get_run: object
    cancel_run: object
    approve_step: object
    reject_step: object
    approvals: object
    personas: object
    current_user: Callable
    workspace_admin_for: Callable


def register_agent_routes(app, deps: AgentHttpDeps) -> None:

    @app.post("/v1/personas/{persona_id}/agent-runs", status_code=202)
    def post_agent_run(
        persona_id: str,
        payload: AgentRunIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        run = deps.start_run(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            goal=payload.goal,
            thread_id=None,
            max_steps=payload.max_steps,
            token_budget=payload.token_budget,
            plan_script=payload.plan_script,
            enqueue=True,
        )
        return {
            "id": run.id,
            "status": run.status.value,
            "version": run.version,
        }

    @app.get("/v1/agent-runs/{run_id}")
    def get_agent_run(
        run_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        return deps.get_run(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            run_id=run_id,
        )

    @app.post("/v1/agent-runs/{run_id}/cancel")
    def cancel_agent_run(
        run_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        return deps.cancel_run(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            run_id=run_id,
        )

    @app.get("/v1/approvals")
    def list_approvals(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if not deps.workspace_admin_for(user, x_tenant_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        items = deps.approvals.list_pending(TenantId(x_tenant_id))
        return {
            "items": [
                {
                    "id": item.id,
                    "run_id": item.run_id,
                    "tool_name": item.tool_name,
                    "status": item.status.value,
                    "reason": item.reason,
                }
                for item in items
            ]
        }

    @app.post("/v1/approvals/{approval_id}/approve")
    def approve_agent_action(
        approval_id: str,
        payload: AgentApprovalIn | None = Body(default=None),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        modified = payload.modified_arguments if payload else None
        return deps.approve_step(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            approval_id=approval_id,
            modified_arguments=modified,
        )

    @app.post("/v1/approvals/{approval_id}/reject")
    def reject_agent_action(
        approval_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        return deps.reject_step(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            approval_id=approval_id,
        )
