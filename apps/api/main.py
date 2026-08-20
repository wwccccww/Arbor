from __future__ import annotations

from fastapi import FastAPI, Header
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
from arbor.application.conversation.send_message import SendMessage
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


def create_app(*, extra_citation: str | None = None, database_url: str | None = None) -> FastAPI:
    session = None
    stores = None
    if database_url:
        from arbor.adapters.outbound.postgres import PostgresSession

        session = PostgresSession.connect(database_url)
        session.reset()
        session.load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json")
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
    send = SendMessage(
        personas=personas,
        memories=memories,
        threads=threads,
        events=events,
        inbox=inbox,
        vectors=vectors,
        llm=ScriptedLLM(extra_citation_memory_id=extra_citation),
        reasoner=ScriptedReasoner(),
        embed=embed,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    app = FastAPI()
    app.state.stores = stores
    app.state.session = session
    app.state.send = send
    app.state.personas = personas

    @app.exception_handler(DomainError)
    async def domain_error(_, exc: DomainError):
        status = 400
        if exc.code == "UNAUTHENTICATED":
            status = 401
        elif exc.code.startswith("FORBIDDEN"):
            status = 403
        elif exc.code == "NOT_FOUND":
            status = 404
        return _error(exc.code, str(exc), status)

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

    @app.get("/v1/personas/{persona_id}")
    def get_persona(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None or x_tenant_id != persona.tenant_id.value:
            raise DomainError("NOT_FOUND", "not found")
        return {"id": persona_id, "display_name": persona.profile.display_name}

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
        caps = _caps_for(persona, user)
        if Capability.READ_MEMORY not in caps:
            raise DomainError("NOT_FOUND", "not found")
        items = memories.list_active(TenantId(x_tenant_id), PersonaId(persona_id))
        return {"items": [{"id": m.id.value, "text": m.text} for m in items]}

    @app.put("/v1/personas/{persona_id}/grants")
    def put_grants(
        persona_id: str,
        payload: GrantsIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        current_user(authorization)
        persona = personas.get(TenantId(x_tenant_id or ""), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        persona.grants = []
        personas.save(persona)
        return {"ok": True, "grants": payload.grants}

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
        }

    return app


def create_app_from_env() -> FastAPI:
    from arbor.env import database_url as env_database_url

    return create_app(database_url=env_database_url() or None)
