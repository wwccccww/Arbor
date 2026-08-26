from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header

from arbor.adapters.inbound.http.schemas import MemberIn, MemberPatchIn, TenantIn
from arbor.adapters.inbound.http.serialization import tenant_json
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId


@dataclass
class TenantHttpDeps:
    list_tenants: Callable
    create_tenant: Callable
    delete_tenant: Callable
    list_members: Callable
    add_member: Callable
    patch_member: Callable
    current_user: Callable


def register_tenant_routes(app, deps: TenantHttpDeps) -> None:
    @app.get("/v1/tenants")
    def get_tenants(authorization: str | None = Header(default=None)):
        user = deps.current_user(authorization)
        actor = UserId(user["user_id"])
        return {"items": [tenant_json(item, actor) for item in deps.list_tenants(user_id=actor)]}

    @app.post("/v1/tenants", status_code=201)
    def post_tenant(
        payload: TenantIn,
        authorization: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        actor = UserId(user["user_id"])
        tenant = deps.create_tenant(user_id=actor, name=payload.name)
        return tenant_json(tenant, actor)

    @app.delete("/v1/tenants/{tenant_id}", status_code=204)
    def remove_tenant(
        tenant_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if x_tenant_id and x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        deps.delete_tenant(tenant_id=TenantId(tenant_id), actor_id=UserId(user["user_id"]))

    @app.get("/v1/tenants/{tenant_id}/members")
    def get_members(
        tenant_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return {
            "items": deps.list_members(tenant_id=TenantId(tenant_id), actor_id=UserId(user["user_id"]))
        }

    @app.post("/v1/tenants/{tenant_id}/members", status_code=201)
    def post_member(
        tenant_id: str,
        payload: MemberIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return deps.add_member(
            tenant_id=TenantId(tenant_id),
            actor_id=UserId(user["user_id"]),
            email=payload.email,
            role=payload.role,
        )

    @app.patch("/v1/tenants/{tenant_id}/members/{user_id}")
    def patch_member_route(
        tenant_id: str,
        user_id: str,
        payload: MemberPatchIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return deps.patch_member(
            tenant_id=TenantId(tenant_id),
            actor_id=UserId(user["user_id"]),
            user_id=UserId(user_id),
            role=payload.role,
        )
