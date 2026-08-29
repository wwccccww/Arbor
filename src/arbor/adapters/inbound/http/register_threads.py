from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from arbor.adapters.inbound.http.chat import read_chat_payload, sse_stream
from arbor.adapters.inbound.http.observability_middleware import bind_request_context
from arbor.adapters.inbound.http.serialization import caps_for, citation_json, public_attachments
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId


@dataclass
class ThreadHttpDeps:
    personas: object
    threads: object
    memories: object
    storage: object
    send: object
    media_to_inbox: object
    create_thread: Callable
    list_threads: Callable
    list_messages: Callable
    export_thread: Callable
    get_chat_attachment: Callable
    max_upload_bytes: int
    current_user: Callable
    resolve_tenant: Callable


def register_thread_routes(app, deps: ThreadHttpDeps) -> None:
    @app.get("/v1/personas/{persona_id}/threads")
    def get_threads(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        items = deps.list_threads(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=caps_for(persona, user),
        )
        return {"items": [{"id": thread.id.value, "persona_id": thread.persona_id.value} for thread in items]}

    @app.post("/v1/personas/{persona_id}/threads", status_code=201)
    def post_thread(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        thread = deps.create_thread(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=caps_for(persona, user),
        )
        return {"id": thread.id.value, "persona_id": thread.persona_id.value}

    @app.get("/v1/threads/{thread_id}/messages")
    def get_messages(
        thread_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        limit: int = Query(default=50),
        offset: int = Query(default=0),
    ):
        user = deps.current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        thread = deps.threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        page = deps.list_messages(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            capabilities=caps_for(persona, user),
            limit=limit,
            offset=offset,
        )
        return {
            "items": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "citations": [citation_json(deps.memories, tenant, c) for c in message.citations],
                    "attachments": public_attachments(message.attachments),
                }
                for message in page.items
            ],
            "total": page.total,
        }

    @app.post("/v1/threads/{thread_id}/messages")
    async def post_message(
        thread_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        stream: bool = Query(default=False),
    ):
        user = deps.current_user(authorization)
        tenant = deps.resolve_tenant(user, x_tenant_id)
        thread = deps.threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "thread not found")
        persona = deps.personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = caps_for(persona, user)
        if Capability.CHAT not in caps:
            raise DomainError("FORBIDDEN_CHAT", "no grant")
        text, attachments = await read_chat_payload(
            request, deps.storage, tenant, thread_id, deps.max_upload_bytes
        )
        chat_media_added = 0
        if Capability.WRITE_MEMORY in caps and attachments:
            for att in attachments:
                uri = att.get("uri") or ""
                fn = att.get("filename") or ""
                if not uri or not fn:
                    continue
                blob = deps.storage.get(uri)
                if not blob:
                    continue
                try:
                    added = deps.media_to_inbox(
                        tenant_id=tenant,
                        user_id=UserId(user["user_id"]),
                        persona_id=thread.persona_id,
                        filename=fn,
                        data=blob,
                        capabilities=caps,
                        use_reasoner_for_facts=False,
                    )
                    chat_media_added += added.inbox_created
                except DomainError:
                    continue
        if stream:
            bind_request_context(
                tenant_id=tenant.value,
                persona_id=thread.persona_id.value,
                thread_id=thread_id,
                actor_id=user["user_id"],
            )
            streamer = deps.send.stream_reply(
                tenant_id=tenant,
                user_id=UserId(user["user_id"]),
                thread_id=ThreadId(thread_id),
                persona_id=thread.persona_id,
                text=text,
                capabilities=caps,
                attachments=attachments,
            )
            return StreamingResponse(
                sse_stream(streamer, extra_inbox_created=chat_media_added),
                media_type="text/event-stream",
            )
        bind_request_context(
            tenant_id=tenant.value,
            persona_id=thread.persona_id.value,
            thread_id=thread_id,
            actor_id=user["user_id"],
        )
        result = deps.send(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            persona_id=thread.persona_id,
            text=text,
            capabilities=caps,
            attachments=attachments,
        )
        return {
            "message_id": result.get("message_id"),
            "request_id": result.get("request_id"),
            "role": "assistant",
            "text": result["text"],
            "citations": result.get("citation_items") or [],
            "injected_memory_ids": result["injected_memory_ids"],
            "inbox_created": (result.get("inbox_added") or 0) + chat_media_added,
            "attachments": result.get("attachments") or [],
            "retrieval_meta": result.get("retrieval_meta") or {},
            "decision_trace": result.get("decision_trace") or {},
            "context_truncation_notes": result.get("context_truncation_notes") or [],
            "tool_results": result.get("tool_results") or [],
        }

    @app.get("/v1/threads/{thread_id}/attachments/{filename}")
    def get_chat_file(
        thread_id: str,
        filename: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant = TenantId(x_tenant_id)
        thread = deps.threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        result = deps.get_chat_attachment(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            filename=filename,
            capabilities=caps_for(persona, user),
        )
        safe_name = result["filename"].replace('"', "")
        return Response(
            content=result["data"],
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
        )

    @app.post("/v1/threads/{thread_id}/export")
    def post_thread_export(
        thread_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant = TenantId(x_tenant_id)
        thread = deps.threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        return deps.export_thread(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            capabilities=caps_for(persona, user),
        )
