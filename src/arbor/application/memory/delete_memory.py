from __future__ import annotations

from arbor.application.memory.consolidation import consolidations_deriving_from, is_consolidation
from arbor.application.storage.object_gc import delete_stored_object, object_uris_from_memory_source
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, UserId
from arbor.observability.noop import NoopObservability


class DeleteMemory:
    def __init__(
        self,
        *,
        personas,
        memories,
        vectors,
        auth: AuthorizationPolicy,
        storage=None,
        observability: object | None = None,
        invalidate_artifacts=None,
    ) -> None:
        self.personas = personas
        self.memories = memories
        self.vectors = vectors
        self.auth = auth
        self.storage = storage
        self.observability = observability
        self.invalidate_artifacts = invalidate_artifacts

    def _invalidate_artifacts(
        self, tenant_id: TenantId, persona_id: PersonaId, user_id: UserId, uri: str
    ) -> None:
        if self.invalidate_artifacts is None:
            return
        self.invalidate_artifacts(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            object_uri=uri,
        )

    def _obs(self):
        return self.observability or NoopObservability()

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        memory_id: MemoryId,
        capabilities: list[Capability] | None = None,
    ) -> None:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.ADMIN not in caps:
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "admin required")
        item = self.memories.get(tenant_id, memory_id)
        if item is None or item.persona_id != persona_id:
            raise DomainError("NOT_FOUND", "not found")
        from_status = item.status.value
        persona_active = self.memories.list_active(tenant_id, persona_id)
        for derived in consolidations_deriving_from(persona_active, memory_id.value):
            self.memories.delete(tenant_id, derived.id)
            self.vectors.delete(tenant_id, derived.id)
        if is_consolidation(item):
            for source_id in (item.source or {}).get("derived_from") or []:
                source = self.memories.get(tenant_id, MemoryId(str(source_id)))
                if source is not None and source.status.value == "superseded":
                    self.memories.delete(tenant_id, source.id)
                    self.vectors.delete(tenant_id, source.id)
        self.memories.delete(tenant_id, memory_id)
        self.vectors.delete(tenant_id, memory_id)
        obs = self._obs()
        obs.event(
            "memory.transition",
            from_status=from_status,
            to_status="deleted",
            type=item.type.value,
            source="api",
        )
        obs.increment(
            "arbor_memory_transitions_total",
            from_status=from_status,
            to_status="deleted",
            type=item.type.value,
        )
        if self.storage is not None:
            for uri in object_uris_from_memory_source(item.source):
                if delete_stored_object(self.storage, uri):
                    self._invalidate_artifacts(tenant_id, persona_id, user_id, uri)
