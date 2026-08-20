from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.identity.tenant import Membership, Role, Tenant
from arbor.domain.identity.user import User
from arbor.domain.shared.ids import TenantId, UserId


def parse_role(raw: str) -> Role:
    try:
        return Role(raw)
    except ValueError as exc:
        raise DomainError("VALIDATION_ERROR", "unknown role") from exc


class ListTenants:
    def __init__(self, tenants) -> None:
        self.tenants = tenants

    def __call__(self, *, user_id: UserId) -> list[Tenant]:
        return self.tenants.list_for_user(user_id)


class CreateTenant:
    def __init__(self, *, tenants, ids) -> None:
        self.tenants = tenants
        self.ids = ids

    def __call__(self, *, user_id: UserId, name: str) -> Tenant:
        label = (name or "").strip()
        if not label:
            raise DomainError("VALIDATION_ERROR", "name required")
        tenant_id = TenantId(self.ids.new_id())
        tenant = Tenant(
            id=tenant_id,
            name=label,
            memberships=[Membership(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)],
        )
        self.tenants.save(tenant)
        return tenant


class DeleteTenant:
    def __init__(self, *, tenants, personas) -> None:
        self.tenants = tenants
        self.personas = personas

    def __call__(self, *, tenant_id: TenantId, actor_id: UserId) -> None:
        tenant = _require_tenant(self.tenants, tenant_id, actor_id)
        tenant.assert_owner(actor_id)
        if self.personas.list(tenant_id):
            raise DomainError("VALIDATION_ERROR", "tenant not empty")
        self.tenants.delete(tenant_id)


class ListMembers:
    def __init__(self, tenants, users) -> None:
        self.tenants = tenants
        self.users = users

    def __call__(self, *, tenant_id: TenantId, actor_id: UserId) -> list[dict]:
        tenant = _require_tenant(self.tenants, tenant_id, actor_id)
        if not tenant.can_admin_workspace(actor_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        items = []
        for membership in tenant.memberships:
            user = self.users.get(membership.user_id)
            items.append(
                {
                    "user": {
                        "id": membership.user_id.value,
                        "email": user.email if user else "",
                    },
                    "role": membership.role.value,
                }
            )
        return items


class AddTenantMember:
    def __init__(self, *, tenants, users, ids) -> None:
        self.tenants = tenants
        self.users = users
        self.ids = ids

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        actor_id: UserId,
        email: str,
        role: str,
    ) -> dict:
        tenant = _require_admin(self.tenants, tenant_id, actor_id)
        address = (email or "").strip().lower()
        if not address:
            raise DomainError("VALIDATION_ERROR", "email required")
        parsed = parse_role(role)
        user = self.users.get_by_email(address)
        if user is None:
            user = User(id=UserId(self.ids.new_id()), email=address)
            self.users.save(user)
        tenant.add_member(user.id, parsed)
        self.tenants.save(tenant)
        return {"user": {"id": user.id.value, "email": user.email}, "role": parsed.value}


class PatchTenantMember:
    def __init__(self, tenants) -> None:
        self.tenants = tenants

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        actor_id: UserId,
        user_id: UserId,
        role: str,
    ) -> dict:
        tenant = _require_admin(self.tenants, tenant_id, actor_id)
        target = tenant.member(user_id)
        if target is None:
            raise DomainError("NOT_FOUND", "not found")
        tenant.demote(user_id, parse_role(role))
        self.tenants.save(tenant)
        return {"user": {"id": user_id.value}, "role": tenant.member(user_id).role.value}


def _require_tenant(tenants, tenant_id: TenantId, actor_id: UserId) -> Tenant:
    tenant = tenants.get(tenant_id)
    if tenant is None or tenant.member(actor_id) is None:
        raise DomainError("NOT_FOUND", "not found")
    return tenant


def _require_admin(tenants, tenant_id: TenantId, actor_id: UserId) -> Tenant:
    tenant = _require_tenant(tenants, tenant_id, actor_id)
    if not tenant.can_admin_workspace(actor_id):
        raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
    return tenant
