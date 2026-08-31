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
