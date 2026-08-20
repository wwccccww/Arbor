from __future__ import annotations

from fastapi import FastAPI, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryThreadRepository,
    InMemoryVectorIndex,
    ScriptedLLM,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.adapters.outbound.deepseek import DeepSeekChatLLM, DeepSeekReasoner, DeepSeekUnavailable
from arbor.application.conversation.send_message import SendMessage
from arbor.application.conversation.threads import CreateThread, ListMessages, ListThreads
from arbor.application.eventgraph.get_tree import GetEventTree
from arbor.application.memory.commands import ConfirmInboxItem, DismissInboxItem
from arbor.application.persona.commands import CreatePersona, PatchPersona, ReplaceGrants
from arbor.application.persona.queries import ListPersonas
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId

TOKENS = {
    "token-a": {
        "user_id": "0a000000-0000-4000-a000-000000000002",
        "tenant_id": "0a000000-0000-4000-a000-000000000001",
        "role": "owner",
        "email": "demo-a@arbor.eval",
    },
    "token-member": {
        "user_id": "0a000000-0000-4000-a000-000000000003",
        "tenant_id": "0a000000-0000-4000-a000-000000000001",
        "role": "member",
        "email": "member-a@arbor.eval",
    },
}

MEMBER_ID = UserId("0a000000-0000-4000-a000-000000000003")
LINXIA_ID = "0a000000-0000-4000-a000-000000000010"


class MessageIn(BaseModel):
    text: str = ""


class GrantsIn(BaseModel):
    grants: list = Field(default_factory=list)


class ConfirmIn(BaseModel):
    mark_key_event: bool = False


class PersonaIn(BaseModel):
    skin: str = "companion"
    display_name: str = ""
    one_liner: str = ""
    personality: dict | None = None
    taboos: list[str] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)


class PersonaPatchIn(BaseModel):
    skin: str | None = None
    display_name: str | None = None
    one_liner: str | None = None
    personality: dict | None = None
    taboos: list[str] | None = None
    relationships: list[dict] | None = None


def _error(code: str, message: str, status: int, request_id: str = "test-request") -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )


def _caps_for(persona, user: dict) -> list[Capability]:
    if user["role"] in {"owner", "admin"}:
        return list(Capability)
    for grant in persona.grants:
        if grant.user_id.value == user["user_id"]:
            return list(grant.capabilities)
    return []


def _workspace_admin(user: dict) -> bool:
    return user["role"] in {"owner", "admin"}


def _persona_json(persona, caps: list[Capability]) -> dict:
    body = {
        "id": persona.id.value,
        "skin": persona.skin,
        "display_name": persona.profile.display_name,
        "one_liner": persona.profile.one_liner,
    }
    if Capability.READ_MEMORY in caps:
        body["taboos"] = list(persona.profile.taboos)
        body["relationships"] = list(persona.profile.relationships)
        body["personality"] = persona.profile.personality
    return body


def create_app(
    *,
    extra_citation: str | None = None,
    database_url: str | None = None,
    llm=None,
    reasoner=None,
) -> FastAPI:
    session = None
    stores = None
    if database_url:
        from arbor.adapters.outbound.postgres import PostgresSession

        session = PostgresSession.connect(database_url)
        session.migrate()
        session.seed_demo_world_if_empty()
        personas = session.personas
        memories = session.memories
        threads = session.threads
        events = session.events
        inbox = session.inbox
        vectors = session.vectors
        embed = session.embed
        linxia = personas.get(TenantId("0a000000-0000-4000-a000-000000000001"), PersonaId(LINXIA_ID))
        if linxia is not None and not any(g.user_id == MEMBER_ID for g in linxia.grants):
            linxia.grants.append(Grant(user_id=MEMBER_ID, capabilities=[Capability.CHAT]))
            personas.save(linxia)
    else:
        stores = InMemoryStores()
        load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
        linxia = stores.personas[LINXIA_ID]
        if not any(g.user_id == MEMBER_ID for g in linxia.grants):
            linxia.grants.append(Grant(user_id=MEMBER_ID, capabilities=[Capability.CHAT]))
        personas = InMemoryPersonaRepository(stores)
        memories = InMemoryMemoryRepository(stores)
        threads = InMemoryThreadRepository(stores)
        events = InMemoryEventGraphRepository(stores)
        inbox = InMemoryInboxRepository(stores)
        vectors = InMemoryVectorIndex(stores, memories)
        embed = FixtureEmbeddingClient()
    ids = SeqIdGenerator()
    send = SendMessage(
        personas=personas,
        memories=memories,
        threads=threads,
        events=events,
        inbox=inbox,
        vectors=vectors,
        llm=llm or ScriptedLLM(extra_citation_memory_id=extra_citation),
        reasoner=reasoner or ScriptedReasoner(),
        embed=embed,
        ids=ids,
        auth=AuthorizationPolicy(),
    )
    confirm = ConfirmInboxItem(
        personas=personas,
        memories=memories,
        inbox=inbox,
        vectors=vectors,
        embed=embed,
        ids=ids,
        auth=AuthorizationPolicy(),
        events=events,
    )
    dismiss = DismissInboxItem(personas=personas, inbox=inbox, auth=AuthorizationPolicy())
    get_tree = GetEventTree(events, memories=memories)
    list_personas = ListPersonas(personas)
    create_persona = CreatePersona(personas=personas, ids=ids, auth=AuthorizationPolicy())
    patch_persona = PatchPersona(personas=personas, auth=AuthorizationPolicy())
    replace_grants = ReplaceGrants(personas=personas, auth=AuthorizationPolicy())
    create_thread = CreateThread(personas=personas, threads=threads, ids=ids, auth=AuthorizationPolicy())
    list_threads = ListThreads(personas=personas, threads=threads, auth=AuthorizationPolicy())
    list_messages = ListMessages(personas=personas, threads=threads, auth=AuthorizationPolicy())
    app = FastAPI()
    app.state.stores = stores
    app.state.session = session
    app.state.send = send
    app.state.personas = personas
    app.state.inbox = inbox
    app.state.confirm = confirm
    app.state.dismiss = dismiss
    app.state.get_tree = get_tree

    @app.exception_handler(DomainError)
    async def domain_error(_, exc: DomainError):
        status = 400
        if exc.code == "UNAUTHENTICATED":
            status = 401
        elif exc.code.startswith("FORBIDDEN"):
            status = 403
        elif exc.code == "NOT_FOUND":
            status = 404
        elif exc.code == "UPSTREAM_UNAVAILABLE":
            status = 503
        return _error(exc.code, str(exc), status)

    @app.exception_handler(DeepSeekUnavailable)
    async def deepseek_error(_, exc: DeepSeekUnavailable):
        return _error("UPSTREAM_UNAVAILABLE", "chat model unavailable", 503)

    def current_user(authorization: str | None):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise DomainError("UNAUTHENTICATED", "missing bearer")
        token = authorization.split(" ", 1)[1]
        user = TOKENS.get(token)
        if not user:
            raise DomainError("UNAUTHENTICATED", "bad token")
        return user

    @app.get("/v1/me")
    def me(authorization: str | None = Header(default=None)):
        user = current_user(authorization)
        return {
            "user": {"id": user["user_id"], "email": user["email"]},
            "tenants": [{"id": user["tenant_id"]}],
        }

    @app.get("/v1/personas")
    def get_personas(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        items = list_personas(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            workspace_admin=_workspace_admin(user),
        )
        return {
            "items": [_persona_json(persona, _caps_for(persona, user)) for persona in items]
        }

    @app.post("/v1/personas", status_code=201)
    def post_persona(
        payload: PersonaIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = create_persona(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            workspace_admin=_workspace_admin(user),
            skin=payload.skin,
            display_name=payload.display_name,
            one_liner=payload.one_liner,
            personality=payload.personality,
            taboos=payload.taboos,
            relationships=payload.relationships,
        )
        return _persona_json(persona, list(Capability))

    @app.get("/v1/personas/{persona_id}")
    def get_persona(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None or x_tenant_id != persona.tenant_id.value:
            raise DomainError("NOT_FOUND", "not found")
        caps = _caps_for(persona, user)
        if not caps:
            raise DomainError("NOT_FOUND", "not found")
        return _persona_json(persona, caps)

    @app.patch("/v1/personas/{persona_id}")
    def patch_persona_route(
        persona_id: str,
        payload: PersonaPatchIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = _caps_for(persona, user)
        if not caps:
            raise DomainError("NOT_FOUND", "not found")
        updated = patch_persona(
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
        )
        return _persona_json(updated, caps)

    @app.get("/v1/personas/{persona_id}/memories")
    def list_memories(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        _require_read(persona, user)
        items = memories.list_active(TenantId(x_tenant_id), PersonaId(persona_id))
        return {"items": [{"id": m.id.value, "text": m.text} for m in items]}

    @app.put("/v1/personas/{persona_id}/grants")
    def put_grants(
        persona_id: str,
        payload: GrantsIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        persona = personas.get(TenantId(x_tenant_id or ""), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = _caps_for(persona, user)
        if not caps:
            raise DomainError("NOT_FOUND", "not found")
        updated = replace_grants(
            tenant_id=TenantId(x_tenant_id or user["tenant_id"]),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            grants=payload.grants,
            capabilities=caps,
        )
        return {
            "ok": True,
            "grants": [
                {
                    "user_id": grant.user_id.value,
                    "capabilities": [cap.value for cap in grant.capabilities],
                }
                for grant in updated.grants
            ],
        }

    @app.get("/v1/personas/{persona_id}/threads")
    def get_threads(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        items = list_threads(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=_caps_for(persona, user),
        )
        return {"items": [{"id": thread.id.value, "persona_id": thread.persona_id.value} for thread in items]}

    @app.post("/v1/personas/{persona_id}/threads", status_code=201)
    def post_thread(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        thread = create_thread(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=_caps_for(persona, user),
        )
        return {"id": thread.id.value, "persona_id": thread.persona_id.value}

    @app.get("/v1/threads/{thread_id}/messages")
    def get_messages(
        thread_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        thread = threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        loaded = list_messages(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            capabilities=_caps_for(persona, user),
        )
        return {
            "items": [
                {
                    "role": message.role,
                    "content": message.content,
                    "citations": [c.memory_id.value for c in message.citations if c.memory_id],
                }
                for message in loaded.messages
            ]
        }

    @app.post("/v1/threads/{thread_id}/messages")
    def post_message(
        thread_id: str,
        payload: MessageIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        thread = threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "thread not found")
        persona = personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = _caps_for(persona, user)
        if Capability.CHAT not in caps:
            raise DomainError("FORBIDDEN_CHAT", "no grant")
        result = send(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            persona_id=thread.persona_id,
            text=payload.text,
            capabilities=caps,
        )
        return {
            "text": result["text"],
            "citations": result["citations"],
            "injected_memory_ids": result["injected_memory_ids"],
            "inbox_created": result.get("inbox_added") or 0,
        }

    def _require_read(persona, user):
        caps = _caps_for(persona, user)
        if Capability.READ_MEMORY not in caps:
            raise DomainError("NOT_FOUND", "not found")
        return caps

    def _require_write(persona, user):
        caps = _caps_for(persona, user)
        if Capability.WRITE_MEMORY not in caps and Capability.ADMIN not in caps:
            raise DomainError("NOT_FOUND", "not found")
        return caps

    @app.get("/v1/personas/{persona_id}/inbox")
    def list_inbox(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        _require_write(persona, user)
        items = inbox.list_pending(TenantId(x_tenant_id), PersonaId(persona_id))
        return {
            "items": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "status": item.status,
                    "payload": item.payload,
                }
                for item in items
            ]
        }

    @app.post("/v1/inbox/{inbox_id}/confirm")
    def confirm_inbox(
        inbox_id: str,
        payload: ConfirmIn | None = None,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        item = inbox.get(tenant, inbox_id)
        if item is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(tenant, item.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = _require_write(persona, user)
        memory = confirm(
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
        user = current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        item = inbox.get(tenant, inbox_id)
        if item is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(tenant, item.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = _require_write(persona, user)
        dismiss(
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
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        _require_read(persona, user)
        tree = get_tree(
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

    return app


def create_app_from_env() -> FastAPI:
    from arbor.env import chat_api_key, database_url as env_database_url

    llm = None
    reasoner = None
    if chat_api_key():
        llm = DeepSeekChatLLM()
        reasoner = DeepSeekReasoner()
    return create_app(database_url=env_database_url() or None, llm=llm, reasoner=reasoner)
