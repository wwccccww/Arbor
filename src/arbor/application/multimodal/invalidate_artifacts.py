"""Invalidate artifact evidence when backing object storage is removed."""

from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class InvalidateArtifactsForObjectUri:
    def __init__(self, *, personas, artifacts, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.artifacts = artifacts
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        object_uri: str,
        capabilities: list[Capability] | None = None,
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.WRITE_MEMORY not in caps and not self.auth.can_write_memory(persona, user_id):
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")
        uri = (object_uri or "").strip()
        if not uri:
            raise DomainError("VALIDATION_ERROR", "object_uri required")
        invalidated: list[str] = []
        for artifact in self.artifacts.list_for_persona(tenant_id, persona_id, limit=500):
            if artifact.object_uri == uri and artifact.status == "active":
                artifact.status = "deleted"
                self.artifacts.save(artifact)
                invalidated.append(artifact.id)
        return {"object_uri": uri, "invalidated_artifact_ids": invalidated}
