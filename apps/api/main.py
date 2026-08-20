from __future__ import annotations

from fastapi import FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryAuditLogRepository,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryObjectStorage,
    InMemoryStores,
    InMemoryTenantRepository,
    InMemoryThreadRepository,
    InMemoryUserRepository,
    InMemoryVectorIndex,
    ScriptedLLM,
    ScriptedReasoner,
    SeqIdGenerator,
    FixedClock,
)
from arbor.adapters.outbound.deepseek import DeepSeekChatLLM, DeepSeekReasoner, DeepSeekUnavailable
from arbor.application.audit.commands import RecordAudit
from arbor.application.audit.queries import ListAuditLogs
from arbor.application.conversation.send_message import SendMessage
from arbor.application.conversation.threads import (
    CreateThread,
    ExportThread,
    GetChatAttachment,
    ListMessages,
    ListThreads,
)
from arbor.application.evaluation.commands import StartEvalRun
from arbor.application.eventgraph.get_card import GetEventCard
from arbor.application.eventgraph.get_tree import GetEventTree
from arbor.application.identity.commands import (
    AddTenantMember,
    CreateTenant,
    DeleteTenant,
    ListMembers,
    ListTenants,
    PatchTenantMember,
)
from arbor.application.memory.commands import ConfirmInboxItem, DismissInboxItem, ImportArtifact, ProcessImportJob
from arbor.application.memory.queries import ListMemories
from arbor.application.persona.commands import CreatePersona, PatchPersona, ReplaceGrants
from arbor.application.persona.queries import ListPersonas
from arbor.domain.errors import DomainError
from arbor.domain.identity.tenant import Membership, Role
from arbor.domain.identity.user import User
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import EventId, PersonaId, TenantId, ThreadId, UserId

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
DEMO_TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA_ID = "0a000000-0000-4000-a000-000000000010"


class MessageIn(BaseModel):
    text: str = ""
    attachments: list = Field(default_factory=list)


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


class MemberPatchIn(BaseModel):
    role: str


class TenantIn(BaseModel):
    name: str = ""


class MemberIn(BaseModel):
    email: str
    role: str = "member"


class EvalRunIn(BaseModel):
    strategy: str
    suite_version: str
    mode: str = "retrieval"


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


def _public_attachments(items) -> list[dict]:
    return [
        {"filename": item["filename"]}
        for item in items or []
        if isinstance(item, dict) and item.get("filename")
    ]


async def _read_chat_payload(request: Request, storage, tenant: TenantId, thread_id: str) -> tuple[str, list]:
    content_type = request.headers.get("content-type") or ""
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text") or "")
        attachments: list[dict] = []
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            data = await upload.read()
            filename = str(getattr(upload, "filename", None) or "upload.bin")
            filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip() or "upload.bin"
            uri = storage.put(f"chat/{tenant.value}/{thread_id}/{filename}", data)
            attachments.append({"filename": filename, "uri": uri})
        return text, attachments
    try:
        body = await request.json()
    except Exception as exc:
        raise DomainError("VALIDATION_ERROR", "invalid json") from exc
    if not isinstance(body, dict):
        raise DomainError("VALIDATION_ERROR", "invalid body")
    payload = MessageIn.model_validate(body)
    return payload.text, list(payload.attachments or [])


def _ensure_demo_member(tenants, users) -> None:
    tenant = tenants.get(DEMO_TENANT)
    if tenant is None:
        return
    if users.get(MEMBER_ID) is None:
        users.save(User(id=MEMBER_ID, email="member-a@arbor.eval"))
    if tenant.member(MEMBER_ID) is None:
        tenant.memberships.append(
            Membership(tenant_id=DEMO_TENANT, user_id=MEMBER_ID, role=Role.MEMBER)
        )
        tenants.save(tenant)


def _tenant_json(tenant, user_id: UserId) -> dict:
    membership = tenant.member(user_id)
    return {
        "id": tenant.id.value,
        "name": tenant.name,
        "role": membership.role.value if membership else None,
    }


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
        audit_logs = session.audit_logs
        tenants = session.tenants
        users = session.users
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
        audit_logs = InMemoryAuditLogRepository(stores)
        tenants = InMemoryTenantRepository(stores)
        users = InMemoryUserRepository(stores)
    _ensure_demo_member(tenants, users)
    ids = SeqIdGenerator()
    record_audit = RecordAudit(logs=audit_logs, ids=ids, clock=FixedClock())
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
        audit=record_audit,
    )
    dismiss = DismissInboxItem(personas=personas, inbox=inbox, auth=AuthorizationPolicy())
    get_tree = GetEventTree(events, memories=memories)
    get_card = GetEventCard(events=events, memories=memories, personas=personas, auth=AuthorizationPolicy())
    list_personas = ListPersonas(personas)
    create_persona = CreatePersona(personas=personas, ids=ids, auth=AuthorizationPolicy())
    patch_persona = PatchPersona(personas=personas, auth=AuthorizationPolicy(), audit=record_audit)
    replace_grants = ReplaceGrants(personas=personas, auth=AuthorizationPolicy())
    create_thread = CreateThread(personas=personas, threads=threads, ids=ids, auth=AuthorizationPolicy())
    list_threads = ListThreads(personas=personas, threads=threads, auth=AuthorizationPolicy())
    list_messages = ListMessages(personas=personas, threads=threads, auth=AuthorizationPolicy())
    export_thread = ExportThread(personas=personas, threads=threads, auth=AuthorizationPolicy(), audit=record_audit)
    object_stores = stores or InMemoryStores()
    storage = InMemoryObjectStorage(object_stores)
    get_chat_attachment = GetChatAttachment(
        personas=personas, threads=threads, storage=storage, auth=AuthorizationPolicy()
    )
    import_artifact = ImportArtifact(personas=personas, storage=storage, auth=AuthorizationPolicy(), audit=record_audit)
    process_import = ProcessImportJob(personas=personas, inbox=inbox, ids=ids, auth=AuthorizationPolicy())
    list_memories = ListMemories(personas=personas, memories=memories, auth=AuthorizationPolicy())
    list_audit_logs = ListAuditLogs(audit_logs)
    list_tenants = ListTenants(tenants)
    create_tenant = CreateTenant(tenants=tenants, ids=ids)
    delete_tenant = DeleteTenant(tenants=tenants, personas=personas)
    list_members = ListMembers(tenants, users)
    add_member = AddTenantMember(tenants=tenants, users=users, ids=ids)
    patch_member = PatchTenantMember(tenants)
    import_jobs: dict[str, dict] = {}
    eval_runs: dict[str, dict] = {}

    def run_retrieval(*, strategy: str, suite_version: str) -> dict:
        from arbor.adapters.inbound.eval_runner import run_suite

        name = "suite-v1" if suite_version == "v1" else "suite-ragas-v1"
        suite_dir = ROOT / "eval" / "fixtures" / name
        try:
            return run_suite(strategy=strategy, suite_dir=suite_dir, backend="memory")
        except FileNotFoundError as exc:
            raise DomainError("VALIDATION_ERROR", "suite files missing") from exc

    start_eval = StartEvalRun(run_retrieval=run_retrieval, ids=ids)
    app = FastAPI()
    app.state.stores = stores
    app.state.session = session
    app.state.send = send
    app.state.personas = personas
    app.state.inbox = inbox
    app.state.confirm = confirm
    app.state.dismiss = dismiss
    app.state.get_tree = get_tree
    app.state.import_jobs = import_jobs
    app.state.eval_runs = eval_runs
    app.state.storage = storage

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
        actor = UserId(user["user_id"])
        return {
            "user": {"id": user["user_id"], "email": user["email"]},
            "tenants": [_tenant_json(item, actor) for item in list_tenants(user_id=actor)],
        }

    @app.get("/v1/tenants")
    def get_tenants(authorization: str | None = Header(default=None)):
        user = current_user(authorization)
        actor = UserId(user["user_id"])
        return {"items": [_tenant_json(item, actor) for item in list_tenants(user_id=actor)]}

    @app.post("/v1/tenants", status_code=201)
    def post_tenant(
        payload: TenantIn,
        authorization: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        actor = UserId(user["user_id"])
        tenant = create_tenant(user_id=actor, name=payload.name)
        return _tenant_json(tenant, actor)

    @app.delete("/v1/tenants/{tenant_id}", status_code=204)
    def remove_tenant(
        tenant_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if x_tenant_id and x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        delete_tenant(tenant_id=TenantId(tenant_id), actor_id=UserId(user["user_id"]))

    @app.get("/v1/tenants/{tenant_id}/members")
    def get_members(
        tenant_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return {
            "items": list_members(tenant_id=TenantId(tenant_id), actor_id=UserId(user["user_id"]))
        }

    @app.post("/v1/tenants/{tenant_id}/members", status_code=201)
    def post_member(
        tenant_id: str,
        payload: MemberIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return add_member(
            tenant_id=TenantId(tenant_id),
            actor_id=UserId(user["user_id"]),
            email=payload.email,
            role=payload.role,
        )

    @app.patch("/v1/tenants/{tenant_id}/members/{user_id}")
    def patch_member_route(
        tenant_id: str,
        user_id: str,
        payload: MemberPatchIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if x_tenant_id != tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return patch_member(
            tenant_id=TenantId(tenant_id),
            actor_id=UserId(user["user_id"]),
            user_id=UserId(user_id),
            role=payload.role,
        )

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
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        page = list_memories(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            capabilities=_caps_for(persona, user),
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

    @app.post("/v1/personas/{persona_id}/imports", status_code=202)
    async def post_import(
        persona_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        file: UploadFile = File(...),
        hint: str | None = Form(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(persona_id))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = _require_write(persona, user)
        data = await file.read()
        filename = file.filename or "upload.bin"
        import_artifact(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            filename=filename,
            data=data,
            capabilities=caps,
        )
        inbox_created = process_import(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            persona_id=PersonaId(persona_id),
            filename=filename,
            data=data,
            hint=hint,
            capabilities=caps,
        )
        job_id = ids.new_id()
        import_jobs[job_id] = {
            "id": job_id,
            "tenant_id": x_tenant_id,
            "persona_id": persona_id,
            "status": "completed",
            "filename": filename,
            "hint": hint,
            "inbox_created": inbox_created,
        }
        return {"job_id": job_id, "status": "completed", "inbox_created": inbox_created}

    @app.get("/v1/imports/{job_id}")
    def get_import(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        job = import_jobs.get(job_id)
        if job is None or job["tenant_id"] != x_tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(TenantId(x_tenant_id), PersonaId(job["persona_id"]))
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        _require_write(persona, user)
        return {
            "id": job["id"],
            "status": job["status"],
            "filename": job["filename"],
            "persona_id": job["persona_id"],
            "inbox_created": job.get("inbox_created", 0),
        }

    @app.post("/v1/eval/runs", status_code=202)
    def post_eval_run(
        payload: EvalRunIn,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        result = start_eval(
            workspace_admin=_workspace_admin(user),
            strategy=payload.strategy,
            suite_version=payload.suite_version,
            mode=payload.mode,
        )
        result["tenant_id"] = x_tenant_id
        eval_runs[result["id"]] = result
        return {"id": result["id"]}

    @app.get("/v1/eval/runs/{run_id}")
    def get_eval_run(
        run_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if not _workspace_admin(user):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        run = eval_runs.get(run_id)
        if run is None or run["tenant_id"] != x_tenant_id:
            raise DomainError("NOT_FOUND", "not found")
        return {
            "id": run["id"],
            "status": run["status"],
            "strategy": run["strategy"],
            "suite_version": run["suite_version"],
            "mode": run["mode"],
            "metrics": run["metrics"],
            "p0_tenant_leak_zero": run["p0_tenant_leak_zero"],
        }

    @app.get("/v1/audit-logs")
    def get_audit_logs(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        action: str | None = Query(default=None),
        persona_id: str | None = Query(default=None),
        since: str | None = Query(default=None),
        until: str | None = Query(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        items = list_audit_logs(
            tenant_id=TenantId(x_tenant_id),
            workspace_admin=_workspace_admin(user),
            action=action,
            persona_id=PersonaId(persona_id) if persona_id else None,
            since=since,
            until=until,
        )
        return {
            "items": [
                {
                    "id": entry.id,
                    "actor_user_id": entry.actor_user_id.value,
                    "action": entry.action,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "persona_id": entry.persona_id.value if entry.persona_id else None,
                    "payload": entry.payload,
                    "created_at": entry.created_at,
                }
                for entry in items
            ]
        }

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
                    "attachments": _public_attachments(message.attachments),
                }
                for message in loaded.messages
            ]
        }

    @app.post("/v1/threads/{thread_id}/messages")
    async def post_message(
        thread_id: str,
        request: Request,
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
        text, attachments = await _read_chat_payload(request, storage, tenant, thread_id)
        result = send(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            persona_id=thread.persona_id,
            text=text,
            capabilities=caps,
            attachments=attachments,
        )
        return {
            "text": result["text"],
            "citations": result["citations"],
            "injected_memory_ids": result["injected_memory_ids"],
            "inbox_created": result.get("inbox_added") or 0,
            "attachments": result.get("attachments") or [],
        }

    @app.get("/v1/threads/{thread_id}/attachments/{filename}")
    def get_chat_file(
        thread_id: str,
        filename: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant = TenantId(x_tenant_id)
        thread = threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        result = get_chat_attachment(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            filename=filename,
            capabilities=_caps_for(persona, user),
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
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant = TenantId(x_tenant_id)
        thread = threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        return export_thread(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            capabilities=_caps_for(persona, user),
        )

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

    @app.get("/v1/events/{event_id}")
    def get_event_card(
        event_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        preview = events.get(TenantId(x_tenant_id), EventId(event_id))
        if preview is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(TenantId(x_tenant_id), preview.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        card = get_card(
            tenant_id=TenantId(x_tenant_id),
            user_id=UserId(user["user_id"]),
            event_id=EventId(event_id),
            capabilities=_caps_for(persona, user),
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
            "attachments": [
                {"id": item.id.value, "type": item.type.value, "text": item.text}
                for item in card["attachments"]
            ],
            "memories": [{"id": item.id.value, "text": item.text} for item in card["memories"]],
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
