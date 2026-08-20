from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


@dataclass
class Membership:
    tenant_id: TenantId
    user_id: UserId
    role: Role


@dataclass
class Tenant:
    id: TenantId
    name: str
    memberships: list[Membership] = field(default_factory=list)

    def owners(self) -> list[Membership]:
        return [m for m in self.memberships if m.role is Role.OWNER]

    def remove_member(self, user_id: UserId) -> None:
        remaining = [m for m in self.memberships if m.user_id != user_id]
        if not any(m.role is Role.OWNER for m in remaining):
            raise DomainError("TENANT_OWNER_REQUIRED", "tenant must keep at least one owner")
        self.memberships = remaining

    def demote(self, user_id: UserId, new_role: Role) -> None:
        if new_role is Role.OWNER:
            for m in self.memberships:
                if m.user_id == user_id:
                    m.role = Role.OWNER
            return
        target = next(m for m in self.memberships if m.user_id == user_id)
        if target.role is Role.OWNER and len(self.owners()) == 1:
            raise DomainError("TENANT_OWNER_REQUIRED", "cannot demote the last owner")
        target.role = new_role

    def can_admin_workspace(self, user_id: UserId) -> bool:
        for m in self.memberships:
            if m.user_id == user_id and m.role in {Role.OWNER, Role.ADMIN}:
                return True
        return False
