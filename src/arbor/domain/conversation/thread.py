from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryItem
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId


@dataclass(frozen=True, slots=True)
class Citation:
    memory_id: MemoryId | None = None
    event_id: EventId | None = None

    def assert_persona(self, thread_persona: PersonaId, memory: MemoryItem | None) -> None:
        if self.memory_id is None:
            return
        if memory is None or memory.persona_id != thread_persona:
            raise DomainError("CITATION_PERSONA_MISMATCH", "citation persona mismatch")


@dataclass
class Message:
    role: str
    content: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class Thread:
    id: ThreadId
    tenant_id: TenantId
    persona_id: PersonaId
    summary: str = ""
    messages: list[Message] = field(default_factory=list)

    def rebind_persona(self, new_persona: PersonaId) -> None:
        if new_persona != self.persona_id:
            raise DomainError("THREAD_PERSONA_IMMUTABLE", "thread cannot change persona")

    def append_message(self, message: Message, *, can_chat: bool) -> None:
        if not can_chat:
            raise DomainError("FORBIDDEN_CHAT", "chat grant required")
        self.messages.append(message)
