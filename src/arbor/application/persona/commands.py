from __future__ import annotations

from arbor.domain.conversation.thread import Thread
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class CreatePersona:
    def __init__(self, *, personas, ids, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.ids = ids
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        workspace_admin: bool,
        skin: str,
        display_name: str,
        one_liner: str = "",
        personality: dict | None = None,
        taboos: list[str] | None = None,
        relationships: list[dict] | None = None,
    ) -> Persona:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        name = (display_name or "").strip()
        if not name:
            raise DomainError("VALIDATION_ERROR", "display_name required")
        persona = Persona(
            id=PersonaId(self.ids.new_id()),
            tenant_id=tenant_id,
            skin=skin or "companion",
            profile=Profile(
                display_name=name,
                one_liner=one_liner or "",
                personality=personality,
                taboos=list(taboos or []),
                relationships=list(relationships or []),
            ),
            grants=[Grant(user_id=user_id, capabilities=list(Capability))],
        )
        self.personas.save(persona)
        return persona


class PatchPersona:
    def __init__(self, *, personas, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        capabilities: list[Capability] | None = None,
        display_name: str | None = None,
        one_liner: str | None = None,
        personality: dict | None = None,
        taboos: list[str] | None = None,
        relationships: list[dict] | None = None,
        skin: str | None = None,
    ) -> Persona:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.ADMIN not in caps:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise DomainError("VALIDATION_ERROR", "display_name required")
            persona.profile.display_name = name
        if one_liner is not None:
            persona.profile.one_liner = one_liner
        if personality is not None:
            persona.profile.personality = personality
        if taboos is not None:
            persona.profile.taboos = list(taboos)
        if relationships is not None:
            persona.profile.relationships = list(relationships)
        if skin is not None:
            persona.skin = skin
        self.personas.save(persona)
        return persona


class ReplaceGrants:
    def __init__(self, *, personas, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        grants: list,
        capabilities: list[Capability] | None = None,
    ) -> Persona:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.ADMIN not in caps:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        parsed = []
        for grant in grants or []:
            parsed.append(
                Grant(
                    user_id=UserId(str(grant["user_id"])),
                    capabilities=self.auth.parse_capabilities(list(grant.get("capabilities") or [])),
                )
            )
        persona.grants = parsed
        self.personas.save(persona)
        return persona
