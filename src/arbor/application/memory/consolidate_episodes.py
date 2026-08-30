"""Merge similar episodic memories into a consolidation item while preserving sources."""

from __future__ import annotations

from arbor.application.memory.consolidation import (
    build_consolidation_text,
    group_similar_episodes,
    is_consolidation,
)
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, UserId


class ConsolidateEpisodicMemories:
    def __init__(
        self,
        *,
        personas,
        memories,
        vectors,
        embed,
        ids,
        auth: AuthorizationPolicy,
    ) -> None:
        self.personas = personas
        self.memories = memories
        self.vectors = vectors
        self.embed = embed
        self.ids = ids
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        min_group_size: int = 2,
        capabilities: list[Capability] | None = None,
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.WRITE_MEMORY not in caps and not self.auth.can_write_memory(persona, user_id):
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")

        active = self.memories.list_active(tenant_id, persona_id)
        groups = group_similar_episodes(active)
        created: list[str] = []
        superseded: list[str] = []

        for group in groups:
            if len(group) < min_group_size:
                continue
            if any(is_consolidation(item) for item in group):
                continue
            derived_ids = [item.id.value for item in group]
            consolidated = MemoryItem(
                id=MemoryId(self.ids.new_id()),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=build_consolidation_text(group),
                type=MemoryType.EPISODE_SUMMARY,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.EPISODIC,
                source={
                    "consolidation": True,
                    "derived_from": derived_ids,
                },
            )
            for item in group:
                item.mark_superseded()
                self.memories.save(item)
                self.vectors.delete(tenant_id, item.id)
                superseded.append(item.id.value)
            self.memories.save(consolidated)
            self.vectors.upsert(
                tenant_id,
                persona_id,
                consolidated.id,
                self.embed.embed(consolidated.text),
                consolidated.status,
            )
            created.append(consolidated.id.value)

        return {
            "created_consolidation_ids": created,
            "superseded_source_ids": superseded,
            "group_count": len(created),
        }
