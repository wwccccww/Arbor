from __future__ import annotations

from arbor.domain.conversation.thread import Thread
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId


class CreateThread:
    def __init__(self, *, personas, threads, ids, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.threads = threads
        self.ids = ids
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        capabilities: list[Capability] | None = None,
    ) -> Thread:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.CHAT not in caps:
            raise DomainError("FORBIDDEN_CHAT", "chat grant required")
        thread = Thread(id=ThreadId(self.ids.new_id()), tenant_id=tenant_id, persona_id=persona_id)
        self.threads.save(thread)
        return thread


class ListThreads:
    def __init__(self, *, personas, threads, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.threads = threads
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        capabilities: list[Capability] | None = None,
    ) -> list[Thread]:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.CHAT not in caps:
            raise DomainError("NOT_FOUND", "not found")
        return self.threads.list(tenant_id, persona_id)


class ListMessages:
    def __init__(self, *, personas, threads, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.threads = threads
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        thread_id: ThreadId,
        capabilities: list[Capability] | None = None,
    ) -> Thread:
        thread = self.threads.get(tenant_id, thread_id)
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = self.personas.get(tenant_id, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.CHAT not in caps:
            raise DomainError("NOT_FOUND", "not found")
        return thread
