from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class MessagePage:
    items: list
    total: int


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
        limit: int = 50,
        offset: int = 0,
    ) -> MessagePage:
        thread = self.threads.get(tenant_id, thread_id)
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = self.personas.get(tenant_id, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.CHAT not in caps:
            raise DomainError("NOT_FOUND", "not found")
        if limit < 1 or limit > 100:
            raise DomainError("VALIDATION_ERROR", "limit must be 1..100")
        if offset < 0:
            raise DomainError("VALIDATION_ERROR", "offset must be >= 0")
        items = list(thread.messages)
        return MessagePage(items=items[offset : offset + limit], total=len(items))


class GetChatAttachment:
    """Return stored chat file bytes. Does not write memory."""

    def __init__(self, *, personas, threads, storage, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.threads = threads
        self.storage = storage
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        thread_id: ThreadId,
        filename: str,
        capabilities: list[Capability] | None = None,
    ) -> dict:
        thread = self.threads.get(tenant_id, thread_id)
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = self.personas.get(tenant_id, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.CHAT not in caps:
            raise DomainError("NOT_FOUND", "not found")
        wanted = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
        if not wanted:
            raise DomainError("NOT_FOUND", "not found")
        uri = None
        for message in thread.messages:
            for item in message.attachments or []:
                if item.get("filename") == wanted and item.get("uri"):
                    uri = item["uri"]
        if not uri:
            raise DomainError("NOT_FOUND", "not found")
        data = self.storage.get(uri)
        if data is None:
            raise DomainError("NOT_FOUND", "not found")
        return {"filename": wanted, "data": data}


class ExportThread:
    """Return conversation JSON and record a sanitized audit row. Does not write memory."""

    def __init__(self, *, personas, threads, auth: AuthorizationPolicy, audit=None) -> None:
        self.personas = personas
        self.threads = threads
        self.auth = auth
        self.audit = audit

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        thread_id: ThreadId,
        capabilities: list[Capability] | None = None,
    ) -> dict:
        thread = self.threads.get(tenant_id, thread_id)
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = self.personas.get(tenant_id, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.CHAT not in caps:
            raise DomainError("NOT_FOUND", "not found")
        body = {
            "id": thread.id.value,
            "persona_id": thread.persona_id.value,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "citations": [c.memory_id.value for c in message.citations if c.memory_id],
                    "attachments": [{"filename": item["filename"]} for item in message.attachments or [] if item.get("filename")],
                }
                for message in thread.messages
            ],
        }
        if self.audit:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                action="thread.export",
                resource_type="thread",
                resource_id=thread.id.value,
                persona_id=thread.persona_id,
                payload={"message_count": len(thread.messages)},
            )
        return body
