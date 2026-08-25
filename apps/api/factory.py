from contextlib import asynccontextmanager
import json
import os
import time

from fastapi import FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.auth_sessions import InMemoryAuthSessionStore
from arbor.adapters.outbound.deepseek import DeepSeekChatLLM, DeepSeekReasoner, DeepSeekUnavailable
from arbor.adapters.outbound.embedding import EmbeddingUnavailable, embedding_client_from_env
from arbor.adapters.outbound.inmemory import (
    FixedClock,
    FixtureEmbeddingClient,
    InMemoryAuditLogRepository,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryTenantRepository,
    InMemoryThreadRepository,
    InMemoryUserRepository,
    InMemoryVectorIndex,
    ScriptedLLM,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.adapters.outbound.job_queue import ArqJobQueue, arq_redis_settings
from arbor.adapters.outbound.job_queue_holder import JobQueueHolder
from arbor.adapters.outbound.object_storage import build_object_storage, object_store_label
from arbor.adapters.outbound.postgres.auth_sessions import PgAuthSessionStore
from arbor.adapters.outbound.postgres.eval_runs import (
    InMemoryEvalRunRepository,
    PgEvalRunRepository,
)
from arbor.adapters.outbound.postgres.import_jobs import (
    InMemoryImportJobRepository,
    PgImportJobRepository,
)
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
from arbor.application.memory.commands import ConfirmInboxItem, DismissInboxItem, ProcessImportJob
from arbor.application.memory.import_jobs import RunImportJob, SubmitImportJob
from arbor.application.memory.queries import ListMemories
from arbor.application.persona.commands import CreatePersona, PatchPersona, ReplaceGrants
from arbor.application.persona.queries import ListPersonas
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import EventId, PersonaId, TenantId, ThreadId, UserId
from arbor.env import data_dir
from arbor.paths import repo_root

from .demo_auth import (
    LINXIA_ID,
    MEMBER_ID,
    TOKENS,
    authenticate_user,
    demo_password_ok,
    ensure_demo_member,
    profile_for_demo_email,
)
from .rate_limit import (
    DEFAULT_RATE_LIMIT_PER_WINDOW,
    DEFAULT_RATE_WINDOW_SECONDS,
    InMemoryRateLimiter,
)

DEFAULT_MAX_UPLOAD_BYTES = 32 * 1024 * 1024


def _reject_oversize(data: bytes, limit: int) -> None:
    if len(data) > limit:
        raise DomainError("VALIDATION_ERROR", "file too large")


def _runtime_info(
    *,
    llm: object,
    database_url: str | None,
    embed: object,
    object_store: str = "local",
    job_queue: str = "sync",
) -> dict[str, str]:
    if isinstance(embed, FixtureEmbeddingClient) or embed is None:
        embed_label = "fixture"
    else:
        embed_label = getattr(embed, "label", "http")
    return {
        "llm": "deepseek" if isinstance(llm, DeepSeekChatLLM) else "scripted",
        "store": "postgres" if database_url else "memory",
        "embed": embed_label,
        "object_store": object_store,
        "job_queue": job_queue,
    }


def _mount_web_ui(app: FastAPI) -> None:
    dist = repo_root() / "apps" / "web" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return

    @app.get("/")
    def web_index():
        return FileResponse(index)

    favicon = dist / "favicon.svg"
    if favicon.is_file():

        @app.get("/favicon.svg")
        def web_favicon():
            return FileResponse(favicon)

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="web-assets")


class MessageIn(BaseModel):
    text: str = ""
    attachments: list = Field(default_factory=list)


class GrantsIn(BaseModel):
    grants: list = Field(default_factory=list)


class ConfirmIn(BaseModel):
    mark_key_event: bool = False


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str = ""


class PersonaIn(BaseModel):
    skin: str = "companion"
    display_name: str = ""
    one_liner: str = ""
    personality: dict | None = None
    taboos: list[str] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    template: str | None = None


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


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_request_id() -> str:
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")
    n = (ms << 80) | rand
    chars = ["0"] * 26
    for i in range(25, -1, -1):
        chars[i] = _CROCKFORD[n & 31]
        n >>= 5
    return "".join(chars)


def _error(code: str, message: str, status: int, request_id: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id or new_request_id()}},
    )


def _caps_for(persona, user: dict) -> list[Capability]:
    if user["role"] in {"owner", "admin"}:
        return list(Capability)
    for grant in persona.grants:
        if grant.user_id.value == user["user_id"]:
            return list(grant.capabilities)
    return []


def _grant_json(grant) -> dict:
    return {
        "user_id": grant.user_id.value,
        "capabilities": [cap.value for cap in grant.capabilities],
    }


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
    if Capability.ADMIN in caps:
        body["grants"] = [_grant_json(grant) for grant in persona.grants]
    return body


def _public_attachments(items) -> list[dict]:
    return [
        {"filename": item["filename"]}
        for item in items or []
        if isinstance(item, dict) and item.get("filename")
    ]


def _citation_json(memories, tenant: TenantId, citation) -> dict:
    """Project a stored citation into the same shape post_message returns, so the
    frontend can show readable previews and jump to the related event."""
    body: dict = {}
    if citation.memory_id:
        body["memory_id"] = citation.memory_id.value
        item = memories.get(tenant, citation.memory_id)
        if item is not None:
            body["preview"] = (item.text or "")[:40]
            if item.event_id:
                body["event_id"] = item.event_id.value
    if citation.event_id:
        body["event_id"] = citation.event_id.value
    return body


async def _sse_stream(streamer):
    """Turn a sync ``stream_reply`` generator into an SSE event stream.

    Emits ``data: {"type":"delta","text":...}`` for each text chunk and a final
    ``data: {"type":"done", ...}`` carrying the persisted message id, citations
    and metadata. ``iter_in_threadpool`` keeps the blocking model calls off the
    event loop.
    """
    from arbor.domain.conversation.stream import StreamFinished

    final: dict | None = None
    async for chunk in iterate_in_threadpool(streamer):
        if isinstance(chunk, StreamFinished):
            final = _parse_stream_finished(chunk.raw)
            continue
        if isinstance(chunk, str) and chunk:
            yield _sse_event({"type": "delta", "text": chunk})
    if final is None:
        final = {"text": ""}
    yield _sse_event(
        {
            "type": "done",
            "message_id": final.get("message_id"),
            "text": final.get("text", ""),
            "citations": final.get("citation_items") or [],
            "injected_memory_ids": final.get("injected_memory_ids") or [],
            "inbox_created": final.get("inbox_added") or 0,
            "attachments": final.get("attachments") or [],
        }
    )


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _parse_stream_finished(raw: str) -> dict:
    """Convert the streamed-final envelope (already the post-message payload
    produced by SendMessage.stream_reply) back into a dict for the SSE ``done``
    event. The ``stream_reply`` generator yields a model JSON envelope, so we
    parse it here."""
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {"text": raw}


async def _read_chat_payload(
    request: Request,
    storage,
    tenant: TenantId,
    thread_id: str,
    max_upload_bytes: int,
) -> tuple[str, list]:
    content_type = request.headers.get("content-type") or ""
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text") or "")
        attachments: list[dict] = []
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            data = await upload.read()
            _reject_oversize(data, max_upload_bytes)
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
    ensure_demo_member(tenants, users)


def _tenant_json(tenant, user_id: UserId) -> dict:
    membership = tenant.member(user_id)
    return {
        "id": tenant.id.value,
        "name": tenant.name,
        "role": membership.role.value if membership else None,
    }


def _highest_seq_id(session) -> int:
    """Return the largest a000-NNN sequence already stored, so the id generator
    resumes past persisted rows instead of colliding after a restart."""
    best = 0
    tables = ("tenants", "users", "personas", "threads", "messages",
              "event_nodes", "memory_items", "inbox_items", "audit_logs")
    try:
        for table in tables:
            row = session.conn.execute(
                f"""
                SELECT MAX(CAST(SUBSTRING(id::text FROM 'a000-([0-9]+)$') AS bigint)) AS n
                FROM {table}
                """
            ).fetchone()
            if row and row.get("n"):
                best = max(best, int(row["n"]))
    except Exception:
        return 0
    return best


def create_app(
    *,
    extra_citation: str | None = None,
    database_url: str | None = None,
    llm=None,
    reasoner=None,
    embed=None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    rate_limit_per_window: int = DEFAULT_RATE_LIMIT_PER_WINDOW,
    rate_window_seconds: int = DEFAULT_RATE_WINDOW_SECONDS,
    redis_url: str | None = None,
) -> FastAPI:
    session = None
    stores = None
    if embed is not None:
        resolved_embed = embed
    elif database_url:
        resolved_embed = embedding_client_from_env()
    else:
        resolved_embed = FixtureEmbeddingClient()
    eval_backend = "postgres" if database_url else "memory"
    if database_url:
        from arbor.adapters.outbound.postgres import PostgresSession

        session = PostgresSession.connect(database_url, embed=resolved_embed)
        session.migrate()
        session.seed_demo_world_if_empty()
        personas = session.personas
        memories = session.memories
        threads = session.threads
        events = session.events
        inbox = session.inbox
        vectors = session.vectors
        resolved_embed = session.embed
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
        if not isinstance(resolved_embed, FixtureEmbeddingClient):
            for item in stores.memories.values():
                if item.is_searchable():
                    vectors.upsert(
                        item.tenant_id,
                        item.persona_id,
                        item.id,
                        resolved_embed.embed(item.text),
                        item.status,
                    )
        audit_logs = InMemoryAuditLogRepository(stores)
        tenants = InMemoryTenantRepository(stores)
        users = InMemoryUserRepository(stores)
    _ensure_demo_member(tenants, users)
    if session is not None:
        import_jobs = PgImportJobRepository(session.conn)
        eval_runs = PgEvalRunRepository(session.conn)
        auth_sessions = PgAuthSessionStore(session.conn, TOKENS)
    else:
        import_jobs = InMemoryImportJobRepository()
        eval_runs = InMemoryEvalRunRepository()
        auth_sessions = InMemoryAuthSessionStore(TOKENS)
    ids = SeqIdGenerator(start=_highest_seq_id(session) if session is not None else 0)
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
        embed=resolved_embed,
        ids=ids,
        auth=AuthorizationPolicy(),
    )
    confirm = ConfirmInboxItem(
        personas=personas,
        memories=memories,
        inbox=inbox,
        vectors=vectors,
        embed=resolved_embed,
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
    storage = build_object_storage(session=session, stores=stores)
    get_chat_attachment = GetChatAttachment(
        personas=personas, threads=threads, storage=storage, auth=AuthorizationPolicy()
    )
    process_import = ProcessImportJob(
        personas=personas,
        inbox=inbox,
        ids=ids,
        auth=AuthorizationPolicy(),
        reasoner=reasoner or ScriptedReasoner(),
    )
    run_import = RunImportJob(
        import_jobs=import_jobs,
        storage=storage,
        process_import=process_import,
    )
    submit_import = SubmitImportJob(
        personas=personas,
        storage=storage,
        import_jobs=import_jobs,
        ids=ids,
        auth=AuthorizationPolicy(),
        audit=record_audit,
    )
    job_queue_holder = JobQueueHolder(run_import)
    list_memories = ListMemories(personas=personas, memories=memories, auth=AuthorizationPolicy())
    list_audit_logs = ListAuditLogs(audit_logs)
    list_tenants = ListTenants(tenants)
    create_tenant = CreateTenant(tenants=tenants, ids=ids)
    delete_tenant = DeleteTenant(tenants=tenants, personas=personas)
    list_members = ListMembers(tenants, users)
    add_member = AddTenantMember(tenants=tenants, users=users, ids=ids)
    patch_member = PatchTenantMember(tenants)

    def run_retrieval(*, strategy: str, suite_version: str) -> dict:
        from arbor.adapters.inbound.eval_runner import run_suite

        name = "suite-v1" if suite_version == "v1" else "suite-ragas-v1"
        suite_dir = ROOT / "eval" / "fixtures" / name
        try:
            return run_suite(strategy=strategy, suite_dir=suite_dir, backend=eval_backend)
        except FileNotFoundError as exc:
            raise DomainError("VALIDATION_ERROR", "suite files missing") from exc

    start_eval = StartEvalRun(run_retrieval=run_retrieval, ids=ids)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = None
        if redis_url:
            from arq.connections import create_pool

            pool = await create_pool(arq_redis_settings(redis_url))
            job_queue_holder.use_arq(ArqJobQueue(pool))
            app.state.arq_pool = pool
        yield
        if pool is not None:
            await pool.close()

    app = FastAPI(lifespan=lifespan)
    limiter = InMemoryRateLimiter(limit=rate_limit_per_window, window_seconds=rate_window_seconds)

    @app.middleware("http")
    async def enforce_rate_limit(request: Request, call_next):
        if request.url.path.startswith("/v1"):
            key = request.headers.get("authorization") or "anon"
            try:
                limiter.check(key)
            except DomainError as exc:
                if exc.code == "RATE_LIMITED":
                    return _error(exc.code, str(exc), 429)
                raise
        return await call_next(request)

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
    app.state.runtime = _runtime_info(
        llm=send.llm,
        database_url=database_url,
        embed=resolved_embed,
        object_store=object_store_label(storage),
        job_queue="redis" if redis_url else "sync",
    )
    app.state.auth_sessions = auth_sessions

    @app.exception_handler(DomainError)
    async def domain_error(_, exc: DomainError):
        status = 400
        if exc.code == "UNAUTHENTICATED":
            status = 401
        elif exc.code.startswith("FORBIDDEN"):
            status = 403
        elif exc.code == "NOT_FOUND":
            status = 404
        elif exc.code in {"CONFLICT_INBOX_STATE", "PERSONA_TENANT_MISMATCH"}:
            status = 409
        elif exc.code == "RATE_LIMITED":
            status = 429
        elif exc.code == "UPSTREAM_UNAVAILABLE":
            status = 503
        return _error(exc.code, str(exc), status)

    @app.exception_handler(DeepSeekUnavailable)
    async def deepseek_error(_, exc: DeepSeekUnavailable):
        return _error("UPSTREAM_UNAVAILABLE", "chat model unavailable", 503)

    @app.exception_handler(EmbeddingUnavailable)
    async def embedding_error(_, exc: EmbeddingUnavailable):
        return _error("UPSTREAM_UNAVAILABLE", "embedding model unavailable", 503)

    def current_user(authorization: str | None):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise DomainError("UNAUTHENTICATED", "missing bearer")
        token = authorization.split(" ", 1)[1]
        user = app.state.auth_sessions.get_profile(token)
        if not user:
            raise DomainError("UNAUTHENTICATED", "bad token")
        return user

    def workspace_admin_for(user: dict, tenant_id: str) -> bool:
        """Workspace-admin intent: allow tenant membership owners/admins, and keep
        global token owners/admins as an escape hatch for cross-tenant visibility."""
        if user["role"] in {"owner", "admin"}:
            return True
        tenant = tenants.get(TenantId(tenant_id))
        if tenant is None:
            return False
        return tenant.can_admin_workspace(UserId(user["user_id"]))

    @app.post("/v1/auth/login")
    def login(payload: LoginIn):
        email = (payload.email or "").strip().lower()
        profile = authenticate_user(users, tenants, email, payload.password)
        if profile is None:
            profile = profile_for_demo_email(email)
            if profile is None or not demo_password_ok(email, payload.password):
                raise DomainError("UNAUTHENTICATED", "bad credentials")
        return app.state.auth_sessions.issue(profile)

    @app.post("/v1/auth/refresh")
    def refresh(payload: RefreshIn):
        tokens = app.state.auth_sessions.refresh_session(payload.refresh_token)
        if tokens is None:
            raise DomainError("UNAUTHENTICATED", "bad refresh token")
        return tokens

    @app.post("/v1/auth/logout")
    def logout(payload: LogoutIn | None = None):
        token = (payload.refresh_token if payload else "") or ""
        app.state.auth_sessions.logout(token)
        return {"ok": True}

    @app.get("/v1/me")
    def me(authorization: str | None = Header(default=None)):
        user = current_user(authorization)
        actor = UserId(user["user_id"])
        return {
            "user": {"id": user["user_id"], "email": user["email"]},
            "tenants": [_tenant_json(item, actor) for item in list_tenants(user_id=actor)],
            "runtime": app.state.runtime,
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
            workspace_admin=workspace_admin_for(user, x_tenant_id),
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
            workspace_admin=workspace_admin_for(user, x_tenant_id),
            skin=payload.skin,
            display_name=payload.display_name,
            one_liner=payload.one_liner,
            personality=payload.personality,
            taboos=payload.taboos,
            relationships=payload.relationships,
            template=payload.template,
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
        _reject_oversize(data, max_upload_bytes)
        job = submit_import(
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
        await job_queue_holder.enqueue_import_job(payload)
        if job_queue_holder.is_async:
            return {
                "job_id": job["id"],
                "status": "pending",
                "inbox_created": 0,
            }
        updated = import_jobs.get(x_tenant_id, job["id"]) or job
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
        user = current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        job = import_jobs.get(x_tenant_id, job_id)
        if job is None:
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
            "error": job.get("error"),
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
            workspace_admin=workspace_admin_for(user, x_tenant_id),
            strategy=payload.strategy,
            suite_version=payload.suite_version,
            mode=payload.mode,
        )
        result["tenant_id"] = x_tenant_id
        eval_runs.save(result)
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
        if not workspace_admin_for(user, x_tenant_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        run = eval_runs.get(x_tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "not found")
        return {
            "id": run["id"],
            "status": run["status"],
            "strategy": run["strategy"],
            "suite_version": run["suite_version"],
            "mode": run["mode"],
            "metrics": run["metrics"],
            "p0_tenant_leak_zero": run["p0_tenant_leak_zero"],
            "cases": run.get("cases", []),
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
            workspace_admin=workspace_admin_for(user, x_tenant_id),
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
            "grants": [_grant_json(grant) for grant in updated.grants],
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
        limit: int = Query(default=50),
        offset: int = Query(default=0),
    ):
        user = current_user(authorization)
        tenant = TenantId(x_tenant_id or user["tenant_id"])
        thread = threads.get(tenant, ThreadId(thread_id))
        if thread is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = personas.get(tenant, thread.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        page = list_messages(
            tenant_id=tenant,
            user_id=UserId(user["user_id"]),
            thread_id=ThreadId(thread_id),
            capabilities=_caps_for(persona, user),
            limit=limit,
            offset=offset,
        )
        return {
            "items": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "citations": [_citation_json(memories, tenant, c) for c in message.citations],
                    "attachments": _public_attachments(message.attachments),
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
        text, attachments = await _read_chat_payload(
            request, storage, tenant, thread_id, max_upload_bytes
        )
        if stream:
            streamer = send.stream_reply(
                tenant_id=tenant,
                user_id=UserId(user["user_id"]),
                thread_id=ThreadId(thread_id),
                persona_id=thread.persona_id,
                text=text,
                capabilities=caps,
                attachments=attachments,
            )
            return StreamingResponse(_sse_stream(streamer), media_type="text/event-stream")
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
            "message_id": result.get("message_id"),
            "role": "assistant",
            "text": result["text"],
            "citations": result.get("citation_items") or [],
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

    _mount_web_ui(app)
    return app


def create_app_from_env() -> FastAPI:
    import logging

    from arbor.env import chat_api_key
    from arbor.env import database_url as env_database_url
    from arbor.env import job_queue_backend, redis_url as env_redis_url

    llm = None
    reasoner = None
    if chat_api_key():
        llm = DeepSeekChatLLM()
        reasoner = DeepSeekReasoner()
    url = env_database_url() or None
    if url:
        from arbor.adapters.outbound.postgres.connection import reachable

        if not reachable(url):
            logging.getLogger("arbor.api").warning(
                "DATABASE_URL is set but Postgres is unreachable; using in-memory store. "
                "Comment out DATABASE_URL in .env, or start "
                "docker compose -f infra/compose/postgres.yml up -d"
            )
            url = None
    redis = env_redis_url() if job_queue_backend() == "redis" else None
    return create_app(
        database_url=url,
        llm=llm,
        reasoner=reasoner,
        embed=embedding_client_from_env(),
        redis_url=redis or None,
    )
