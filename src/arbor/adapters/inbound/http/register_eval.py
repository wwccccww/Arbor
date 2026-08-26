from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class EvalHttpDeps:
    eval_runs: object
    start_eval: object
    start_persona_eval: object
    seed_eval_world: object
    personas: object
    session: object | None
    stores: object | None
    current_user: Callable
    workspace_admin_for: Callable
    resolve_tenant: Callable | None = None


from arbor.adapters.inbound.http.schemas import EvalRunIn, PersonaEvalIn
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def register_eval_routes(app, deps: EvalHttpDeps) -> None:
    from fastapi import Body, Header

    @app.post("/v1/eval/seed-world")
    def post_eval_seed_world(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if not deps.workspace_admin_for(user, x_tenant_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        return deps.seed_eval_world(
            suite_version="v1",
            session=deps.session,
            stores=deps.stores,
        )

    @app.post("/v1/eval/runs", status_code=202)
    def post_eval_run(
        payload: EvalRunIn = Body(),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        result = deps.start_eval(
            workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            strategy=payload.strategy,
            suite_version=payload.suite_version,
            mode=payload.mode,
        )
        result["tenant_id"] = x_tenant_id
        deps.eval_runs.save(result)
        return {"id": result["id"]}

    @app.get("/v1/eval/runs/{run_id}")
    def get_eval_run(
        run_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if not deps.workspace_admin_for(user, x_tenant_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        run = deps.eval_runs.get(x_tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "not found")
        return {
            "id": run["id"],
            "status": run["status"],
            "strategy": run["strategy"],
            "suite_version": run["suite_version"],
            "mode": run["mode"],
            "metrics": run.get("metrics") or {},
            "p0_tenant_leak_zero": run.get("p0_tenant_leak_zero"),
            "cases": run.get("cases") or [],
        }

    @app.post("/v1/personas/{persona_id}/eval/runs", status_code=202)
    def post_persona_eval_run(
        persona_id: str,
        payload: PersonaEvalIn = Body(),
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
        result = deps.start_persona_eval(
            workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            strategy=payload.strategy,
        )
        result["tenant_id"] = tenant.value
        deps.eval_runs.save(result)
        return {"id": result["id"]}
