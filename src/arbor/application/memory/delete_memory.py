from __future__ import annotations

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
    ) -> None:
        self.personas = personas
        self.memories = memories
        self.vectors = vectors
        self.auth = auth
        self.storage = storage
        self.observability = observability

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
                delete_stored_object(self.storage, uri)
