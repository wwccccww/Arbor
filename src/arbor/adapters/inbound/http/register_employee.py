from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


@dataclass
class EmployeeHttpDeps:
    get_definition: object
    list_templates: object
    current_user: Callable
    workspace_admin_for: Callable | None = None
    start_employee_eval: object | None = None
    list_versions: object | None = None
    create_draft: object | None = None
    publish_definition: object | None = None


def register_employee_routes(app, deps: EmployeeHttpDeps) -> None:

    @app.get("/v1/employee-templates")
    def list_employee_templates(authorization: str | None = Header(default=None)):
        deps.current_user(authorization)
        return deps.list_templates()

    @app.get("/v1/personas/{persona_id}/employee-definition")
    def get_employee_definition(
        persona_id: str,
        version: str | None = None,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        return deps.get_definition(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            version=version,
        )

    if deps.list_versions is not None:

        @app.get("/v1/personas/{persona_id}/employee-definitions")
        def list_employee_definition_versions(
            persona_id: str,
            authorization: str | None = Header(default=None),
            x_tenant_id: str | None = Header(default=None),
        ):
            user = deps.current_user(authorization)
            if not x_tenant_id:
                raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
            return deps.list_versions(
                tenant_id=TenantId(x_tenant_id),
                user_id=UserId(user["user_id"]),
                persona_id=PersonaId(persona_id),
            )

    if deps.create_draft is not None and deps.workspace_admin_for is not None:

        @app.post("/v1/personas/{persona_id}/employee-definitions", status_code=201)
        def post_employee_definition_draft(
            persona_id: str,
            body: dict,
            authorization: str | None = Header(default=None),
            x_tenant_id: str | None = Header(default=None),
        ):
            user = deps.current_user(authorization)
            if not x_tenant_id:
                raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
            return deps.create_draft(
                tenant_id=TenantId(x_tenant_id),
                user_id=UserId(user["user_id"]),
                persona_id=PersonaId(persona_id),
                version=str(body.get("version") or ""),
                role=str(body.get("role") or ""),
                goals=list(body.get("goals") or []),
                skills=list(body.get("skills") or []),
                knowledge_scopes=list(body.get("knowledge_scopes") or []),
                tool_policy=dict(body.get("tool_policy") or {}),
                approval_policy=dict(body.get("approval_policy") or {}),
                memory_policy=dict(body.get("memory_policy") or {}),
                escalation_policy=dict(body.get("escalation_policy") or {}),
                run_budget_policy=dict(body.get("run_budget_policy") or {}),
                evaluation_suite=str(body.get("evaluation_suite") or "agent-v1"),
                workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            )

    if deps.publish_definition is not None and deps.workspace_admin_for is not None:

        @app.post("/v1/personas/{persona_id}/employee-definitions/{version}/publish", status_code=200)
        def post_publish_employee_definition(
            persona_id: str,
            version: str,
            authorization: str | None = Header(default=None),
            x_tenant_id: str | None = Header(default=None),
        ):
            user = deps.current_user(authorization)
            if not x_tenant_id:
                raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
            return deps.publish_definition(
                tenant_id=TenantId(x_tenant_id),
                user_id=UserId(user["user_id"]),
                persona_id=PersonaId(persona_id),
                version=version,
                workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            )

    if deps.start_employee_eval is not None and deps.workspace_admin_for is not None:

        @app.post("/v1/personas/{persona_id}/employee-eval", status_code=200)
        def post_employee_eval(
            persona_id: str,
            version: str | None = None,
            authorization: str | None = Header(default=None),
            x_tenant_id: str | None = Header(default=None),
        ):
            user = deps.current_user(authorization)
            if not x_tenant_id:
                raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
            return deps.start_employee_eval(
                tenant_id=TenantId(x_tenant_id),
                user_id=UserId(user["user_id"]),
                persona_id=PersonaId(persona_id),
                version=version,
                workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            )
