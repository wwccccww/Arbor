from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId


class MemoryType(str, Enum):
    FACT = "fact"
    EPISODE_SUMMARY = "episode_summary"
    FILE_CHUNK = "file_chunk"
    IMAGE_CAPTION = "image_caption"
    TRANSCRIPT = "transcript"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


@dataclass
class MemoryItem:
    id: MemoryId
    tenant_id: TenantId
    persona_id: PersonaId
    text: str
    type: MemoryType = MemoryType.FACT
    status: MemoryStatus = MemoryStatus.ACTIVE
    event_id: EventId | None = None
    thread_id: ThreadId | None = None
    supersedes: MemoryId | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.persona_id:
            raise DomainError("VALIDATION_ERROR", "memory requires tenant_id and persona_id")

    def is_searchable(self) -> bool:
        return self.status is MemoryStatus.ACTIVE

    def mark_superseded(self) -> None:
        self.status = MemoryStatus.SUPERSEDED


@dataclass
class InboxItem:
    id: str
    tenant_id: TenantId
    persona_id: PersonaId
    kind: str
    payload: dict
    status: str = "pending"
    conflicts_with: MemoryId | None = None

    def confirm(self, new_memory: MemoryItem, old: MemoryItem | None) -> MemoryItem:
        if self.status != "pending":
            raise DomainError("CONFLICT_INBOX_STATE", "inbox item is not pending")
        self.status = "confirmed"
        if old is not None:
            old.mark_superseded()
            new_memory.supersedes = old.id
        return new_memory

    def dismiss(self) -> None:
        if self.status != "pending":
            raise DomainError("CONFLICT_INBOX_STATE", "inbox item is not pending")
        self.status = "dismissed"
