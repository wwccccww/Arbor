from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.errors import DomainError
from arbor.domain.identity.tenant import Tenant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class Capability(str, Enum):
    CHAT = "chat"
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    ADMIN = "admin"


ALLOWED_CAPABILITIES = frozenset(Capability)


@dataclass
class Profile:
    display_name: str
    one_liner: str = ""
    personality: dict | None = None
    taboos: list[str] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    locale: str = "zh-CN"
    avatar: str = ""


@dataclass
class Grant:
    user_id: UserId
    capabilities: list[Capability]


@dataclass
class ToolPolicy:
    allowed_tools: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Persona:
    id: PersonaId
    tenant_id: TenantId
    skin: str
    profile: Profile
    grants: list[Grant] = field(default_factory=list)
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)

    def change_tenant(self, new_tenant: TenantId) -> None:
        if new_tenant != self.tenant_id:
            raise DomainError("PERSONA_TENANT_IMMUTABLE", "persona cannot change tenant")


class AuthorizationPolicy:
    @staticmethod
    def parse_capabilities(raw: list[str]) -> list[Capability]:
        out = []
        for item in raw:
            cap = Capability(item) if not isinstance(item, Capability) else item
            if cap not in ALLOWED_CAPABILITIES:
                raise DomainError("VALIDATION_ERROR", f"unknown capability {cap}")
            out.append(cap)
        return out

    def __init__(self, tenant: Tenant | None = None) -> None:
        self._tenant = tenant

    def _workspace_admin(self, user_id: UserId) -> bool:
        return bool(self._tenant and self._tenant.can_admin_workspace(user_id))

    def capabilities_for(self, persona: Persona, user_id: UserId) -> list[Capability]:
        if self._workspace_admin(user_id):
            return list(Capability)
        for grant in persona.grants:
            if grant.user_id == user_id:
                return list(grant.capabilities)
        return []

    def can_chat(self, persona: Persona, user_id: UserId) -> bool:
        return Capability.CHAT in self.capabilities_for(persona, user_id)

    def can_read_memory(self, persona: Persona, user_id: UserId) -> bool:
        return Capability.READ_MEMORY in self.capabilities_for(persona, user_id)

    def can_write_memory(self, persona: Persona, user_id: UserId) -> bool:
        return Capability.WRITE_MEMORY in self.capabilities_for(persona, user_id)

    def can_admin_persona(self, persona: Persona, user_id: UserId) -> bool:
        return Capability.ADMIN in self.capabilities_for(persona, user_id)
