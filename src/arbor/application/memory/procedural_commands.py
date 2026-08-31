"""Admin workflow to publish procedural memory (draft → review → publish)."""

from __future__ import annotations

from datetime import UTC, datetime

from arbor.application.audit.commands import RecordAudit
from arbor.application.memory.procedural_memory import is_procedural_draft
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryClass, MemoryStatus
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class PublishProceduralMemory:
    def __init__(self, *, personas, memories, auth: AuthorizationPolicy, audit: RecordAudit | None = None):
        self.personas = personas
        self.memories = memories
        self.auth = auth
        self.audit = audit

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        memory_id: MemoryId,
        workspace_admin: bool = False,
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.ADMIN not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        item = self.memories.get(tenant_id, memory_id)
        if item is None or item.persona_id != persona_id:
            raise DomainError("NOT_FOUND", "memory not found")
        if item.memory_class != MemoryClass.PROCEDURAL:
            raise DomainError("VALIDATION_ERROR", "not procedural memory")
        if not is_procedural_draft(item):
            raise DomainError("VALIDATION_ERROR", "procedural memory is not draft")
        source = dict(item.source or {})
        version = str(source.get("version") or "v1")
        for other in self.memories.list_active(tenant_id, persona_id):
            if other.memory_class != MemoryClass.PROCEDURAL or other.id == item.id:
                continue
            other_source = other.source or {}
            if other_source.get("published") and str(other_source.get("version") or "") == version:
                other_source = dict(other_source)
                other_source["superseded"] = True
                other_source["published"] = False
                other.source = other_source
                self.memories.save(other)
        source["draft"] = False
        source["published"] = True
        source["published_at"] = _now_iso()
        item.source = source
        item.status = MemoryStatus.ACTIVE
        self.memories.save(item)
        if self.audit is not None:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                persona_id=persona_id,
                action="procedural_memory.publish",
                resource_type="memory",
                resource_id=memory_id.value,
                payload={"version": version},
            )
        return {
            "memory_id": memory_id.value,
            "version": version,
            "published": True,
        }
