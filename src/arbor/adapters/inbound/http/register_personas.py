from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import File, Form, Header, Query, Response, UploadFile

from arbor.adapters.inbound.http.authz import require_read, require_write
from arbor.adapters.inbound.http.chat import reject_oversize
from arbor.adapters.inbound.http.schemas import ConfirmIn, GrantsIn, PersonaIn, PersonaPatchIn
from arbor.adapters.inbound.http.serialization import caps_for, grant_json, persona_json
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import Capability
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, UserId


@dataclass
class PersonaHttpDeps:
    personas: object
    memories: object
    inbox: object
    events: object
    import_jobs: object
    job_queue_holder: object
    list_personas: Callable
    create_persona: Callable
    patch_persona: Callable
    replace_grants: Callable
    list_memories: Callable
    delete_memory: Callable
    submit_import: Callable
    bootstrap_inbox: Callable
    confirm: Callable
    dismiss: Callable
    get_tree: Callable
    get_card: Callable
    max_upload_bytes: int
    current_user: Callable
    workspace_admin_for: Callable
    resolve_tenant: Callable


def register_persona_routes(app, deps: PersonaHttpDeps) -> None:
    @app.get("/v1/personas")
    def get_personas(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        items = deps.list_personas(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
        )
        return {
            "items": [persona_json(persona, caps_for(persona, user)) for persona in items]
        }

    @app.post("/v1/personas", status_code=201)
    def post_persona(
        payload: PersonaIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.create_persona(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            skin=payload.skin,
            display_name=payload.display_name,
            one_liner=payload.one_liner,
            personality=payload.personality,
            taboos=payload.taboos,
            relationships=payload.relationships,
            template=payload.template,
            avatar=payload.avatar,
        )
        return persona_json(persona, list(Capability))

    @app.get("/v1/personas/{persona_id}")
    def get_persona(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None or x_tenant_id != persona.tenant_id.value:
            raise DomainError("NOT_FOUND", "not found")
        caps = caps_for(persona, user)
        if not caps:
            raise DomainError("NOT_FOUND", "not found")
        return persona_json(persona, caps)

    @app.patch("/v1/personas/{persona_id}")
    def patch_persona_route(
        persona_id: str,
        payload: PersonaPatchIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = caps_for(persona, user)
        if not caps:
            raise DomainError("NOT_FOUND", "not found")
        updated = deps.patch_persona(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=caps,
            display_name=payload.display_name,
            one_liner=payload.one_liner,
            personality=payload.personality,
            taboos=payload.taboos,
            relationships=payload.relationships,
            skin=payload.skin,
            tool_policy=payload.tool_policy,
            avatar=payload.avatar,
        )
        return persona_json(updated, caps)

    @app.get("/v1/personas/{persona_id}/memories")
    def get_memories(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        type: str | None = Query(default=None),
        event_id: str | None = Query(default=None),
        status: str | None = Query(default="active"),
        limit: int = Query(default=50),
        offset: int = Query(default=0),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        page = deps.list_memories(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=caps_for(persona, user),
            memory_type=type,
            event_id=event_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [
                {
                    "id": item.id.value,
                    "text": item.text,
                    "type": item.type.value,
                    "status": item.status.value,
                    "event_id": item.event_id.value if item.event_id else None,
                }
                for item in page.items
            ],
            "total": page.total,
        }

    @app.delete("/v1/personas/{persona_id}/memories/{memory_id}", status_code=204)
    def remove_memory(
        persona_id: str,
        memory_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        tenant = deps.resolve_tenant(user, x_tenant_id)
        persona = deps.personas.get(tenant, PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        deps.delete_memory(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            memory_id=MemoryId(memory_id),
            capabilities=caps_for(persona, user),
        )
        return Response(status_code=204)

    @app.post("/v1/personas/{persona_id}/imports", status_code=202)
    async def post_import(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        file: UploadFile = File(...),
        hint: str | None = Form(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = require_write(persona, user)
        data = await file.read()
        reject_oversize(data, deps.max_upload_bytes)
        job = deps.submit_import(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            filename=file.filename or "upload.bin",
            data=data,
            hint=hint,
            capabilities=caps,
        )
        payload = {
            "job_id": job["id"],
            "tenant_id": x_tenant_id,
            "persona_id": persona_id,
            "object_uri": job["object_uri"],
            "filename": job["filename"],
            "hint": hint,
            "user_id": user["user_id"],
        }
        await deps.job_queue_holder.enqueue_import_job(payload)
        if deps.job_queue_holder.is_async:
            return {
                "job_id": job["id"],
                "status": "pending",
                "inbox_created": 0,
            }
        updated = deps.import_jobs.get(x_tenant_id, job["id"]) or job
        return {
            "job_id": updated["id"],
            "status": updated.get("status", "completed"),
            "inbox_created": int(updated.get("inbox_created") or 0),
        }

    @app.get("/v1/imports/{job_id}")
    def get_import(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        job = deps.import_jobs.get(x_tenant_id, job_id)
        if job is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(job["persona_id"]))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        require_write(persona, user)
        return {
            "id": job["id"],
            "status": job["status"],
            "filename": job["filename"],
            "persona_id": job["persona_id"],
            "inbox_created": job.get("inbox_created", 0),
            "error": job.get("error"),
            "parser": job.get("parser"),
            "media_kind": job.get("media_kind"),
            "chunks_parsed": job.get("chunks_parsed", 0),
        }

    @app.put("/v1/personas/{persona_id}/grants")
    def put_grants(
        persona_id: str,
        payload: GrantsIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        persona = deps.personas.get(TenantId(x_tenant_id or ""), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = caps_for(persona, user)
        if not caps:
            raise DomainError("NOT_FOUND", "not found")
        updated = deps.replace_grants(
            tenant_id=TenantId(x_tenant_id or user["tenant_id"]),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            grants=payload.grants,
            capabilities=caps,
        )
        return {
            "ok": True,
            "grants": [grant_json(grant) for grant in updated.grants],
        }

    @app.get("/v1/personas/{persona_id}/inbox")
    def list_inbox(
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
        require_write(persona, user)
        items = deps.inbox.list_pending(TenantId(x_tenant_id), PersonaId(persona_id))
        return {
            "items": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "status": item.status,
                    "payload": item.payload,
                    "conflicts_with": item.payload.get("conflicts_with"),
                }
                for item in items
            ]
        }

    @app.post("/v1/personas/{persona_id}/inbox/bootstrap")
    def bootstrap_persona_inbox(
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
        caps = require_write(persona, user)
        return deps.bootstrap_inbox(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=caps,
        )

    @app.post("/v1/inbox/{inbox_id}/confirm")
    def confirm_inbox(
        inbox_id: str,
        payload: ConfirmIn | None = None,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        item = deps.inbox.get(tenant, inbox_id)
        if item is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(tenant, item.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = require_write(persona, user)
        memory = deps.confirm(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            persona_id=item.persona_id,
            inbox_id=inbox_id,
            capabilities=caps,
            mark_key_event=bool(payload.mark_key_event) if payload else False,
        )
        body = {"id": memory.id.value, "text": memory.text}
        if memory.event_id:
            body["event_id"] = memory.event_id.value
        return body

    @app.post("/v1/inbox/{inbox_id}/dismiss")
    def dismiss_inbox(
        inbox_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        item = deps.inbox.get(tenant, inbox_id)
        if item is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(tenant, item.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = require_write(persona, user)
        deps.dismiss(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            persona_id=item.persona_id,
            inbox_id=inbox_id,
            capabilities=caps,
        )
        return {"ok": True}

    @app.get("/v1/personas/{persona_id}/events/tree")
    def list_event_tree(
        persona_id: str,
        view: str = Query(default="tree"),
        key_only: bool = Query(default=True),
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = deps.personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        require_read(persona, user)
        tree = deps.get_tree(
            tenant_id=TenantId(x_tenant_id),
            persona_id=PersonaId(persona_id),
            view=view,
            key_only=key_only,
        )
        memory_ids = tree.get("memory_ids") or {}
        return {
            "nodes": [
                {
                    "id": node.id.value,
                    "title": node.title,
                    "happened_at": node.happened_at,
                    "type": node.type,
                    "importance": node.importance,
                    "summary": node.summary,
                    "confidence": node.confidence,
                    "memory_ids": memory_ids.get(node.id.value, []),
                }
                for node in tree["nodes"]
            ],
            "edges": [
                {
                    "from_id": edge.from_id.value,
                    "to_id": edge.to_id.value,
                    "kind": edge.kind,
                }
                for edge in tree["edges"]
            ],
        }

    @app.get("/v1/events/{event_id}")
    def get_event_card(
        event_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        preview = deps.events.get(TenantId(x_tenant_id), EventId(event_id))
        if preview is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = deps.personas.get(TenantId(x_tenant_id), preview.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        card = deps.get_card(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            event_id=EventId(event_id),
            capabilities=caps_for(persona, user),
        )
        node = card["node"]
        return {
            "id": node.id.value,
            "persona_id": node.persona_id.value,
            "title": node.title,
            "happened_at": node.happened_at,
            "type": node.type,
            "importance": node.importance,
            "summary": node.summary,
            "confidence": node.confidence,
            "participants": list(card.get("participants") or []),
            "causal_in": list(card.get("causal_in") or []),
            "causal_out": list(card.get("causal_out") or []),
            "verbatim": [{"id": item.id.value, "text": item.text} for item in card.get("verbatim") or []],
            "attachments": [
                {"id": item.id.value, "type": item.type.value, "text": item.text}
                for item in card["attachments"]
            ],
            "memories": [{"id": item.id.value, "text": item.text} for item in card["memories"]],
        }
