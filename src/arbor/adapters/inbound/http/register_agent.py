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
    list_runs: object
    get_steps: object
    resume_run: object
    cancel_run: object
    approve_step: object
    reject_step: object
    approvals: object
    personas: object
    agent_runs: object
    agent_job_queue: object
    current_user: Callable
    workspace_admin_for: Callable
    start_agent_eval: object | None = None


def register_agent_routes(app, deps: AgentHttpDeps) -> None:

    @app.post("/v1/personas/{persona_id}/agent-runs", status_code=202)
    async def post_agent_run(
        persona_id: str,
        payload: AgentRunIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant_id = TenantId(x_tenant_id)
        user_id = UserId(user["user_id"])
        run = deps.start_run(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=PersonaId(persona_id),
            goal=payload.goal,
            thread_id=None,
            max_steps=payload.max_steps,
            token_budget=payload.token_budget,
            plan_script=payload.plan_script,
            enqueue=False,
        )
        deps.agent_job_queue.bind_actor(tenant_id, user_id)
        if deps.agent_job_queue.is_async:
            await deps.agent_job_queue.enqueue_run_async(tenant_id, run.id, run.version)
        else:
            deps.agent_job_queue.enqueue_run(tenant_id, run.id, run.version)
        fresh = deps.agent_runs.get(tenant_id, run.id) or run
        return {
            "id": fresh.id,
            "status": fresh.status.value,
            "version": fresh.version,
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

    @app.get("/v1/personas/{persona_id}/agent-runs")
    def list_persona_agent_runs(
        persona_id: str,
        limit: int = 20,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        return deps.list_runs(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            limit=limit,
        )

    @app.get("/v1/agent-runs/{run_id}/steps")
    def get_agent_run_steps(
        run_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        return deps.get_steps(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            run_id=run_id,
        )

    @app.post("/v1/agent-runs/{run_id}/resume")
    async def resume_agent_run(
        run_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant_id = TenantId(x_tenant_id)
        user_id = UserId(user["user_id"])
        result = deps.resume_run(
            tenant_id=tenant_id,
            user_id=user_id,
            run_id=run_id,
            enqueue=False,
        )
        deps.agent_job_queue.bind_actor(tenant_id, user_id)
        run = deps.agent_runs.get(tenant_id, run_id)
        if run is not None and not run.is_terminal():
            if deps.agent_job_queue.is_async:
                await deps.agent_job_queue.enqueue_run_async(tenant_id, run.id, run.version)
            else:
                deps.agent_job_queue.enqueue_run(tenant_id, run.id, run.version)
        return result

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

    if deps.start_agent_eval is not None:

        @app.post("/v1/agent-eval/runs", status_code=200)
        def post_agent_eval_run(
            authorization: str | None = Header(default=None),
            x_tenant_id: str | None = Header(default=None),
        ):
            user = deps.current_user(authorization)
            if not x_tenant_id:
                raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
            return deps.start_agent_eval(
                workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
                tenant_id=x_tenant_id,
            )
