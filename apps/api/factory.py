import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.inbound.http.errors import error_response
from arbor.adapters.inbound.http.observability_middleware import (
    register_observability_middleware,
)
from arbor.adapters.inbound.http.register_audit import AuditHttpDeps, register_audit_routes
from arbor.adapters.inbound.http.register_auth import AuthHttpDeps, register_auth_routes
from arbor.adapters.inbound.http.register_eval import EvalHttpDeps, register_eval_routes
from arbor.adapters.inbound.http.register_feishu import FeishuHttpDeps, register_feishu_routes
from arbor.adapters.inbound.http.register_observability import (
    ObservabilityHttpDeps,
    register_observability_routes,
)
from arbor.adapters.inbound.http.register_personas import PersonaHttpDeps, register_persona_routes
from arbor.adapters.inbound.http.register_tenants import TenantHttpDeps, register_tenant_routes
from arbor.adapters.inbound.http.register_threads import ThreadHttpDeps, register_thread_routes
from arbor.adapters.inbound.http.register_tools import ToolsHttpDeps, register_tools_routes
from arbor.adapters.outbound.auth_sessions import InMemoryAuthSessionStore
from arbor.adapters.outbound.deepseek import DeepSeekChatLLM, DeepSeekReasoner, DeepSeekUnavailable
from arbor.adapters.outbound.embedding import EmbeddingUnavailable, embedding_client_from_env
from arbor.adapters.outbound.inmemory import (
    FixedClock,
    FixtureEmbeddingClient,
    InMemoryAuditLogRepository,
    InMemoryDecisionTraceRepository,
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
from arbor.adapters.outbound.multimodal.factory import parse_media_bytes
from arbor.adapters.outbound.object_storage import build_object_storage, object_store_label
from arbor.adapters.outbound.postgres.auth_sessions import PgAuthSessionStore
from arbor.adapters.outbound.postgres.decision_traces import PgDecisionTraceRepository
from arbor.adapters.outbound.postgres.eval_runs import (
    InMemoryEvalRunRepository,
    PgEvalRunRepository,
)
from arbor.adapters.outbound.postgres.import_jobs import (
    InMemoryImportJobRepository,
    PgImportJobRepository,
)
from arbor.adapters.outbound.tools.credential_store import FileFeishuCredentialStore
from arbor.adapters.outbound.tools.feishu_calendar import FeishuCalendarTool, StubCalendarTool
from arbor.adapters.outbound.tools.feishu_client import FeishuClient
from arbor.adapters.outbound.tools.http_ticket import HttpTicketTool
from arbor.adapters.outbound.tools.stub_ticket import StubTicketTool
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
from arbor.application.evaluation.commands import StartEvalRun, StartPersonaEvalRun
from arbor.application.evaluation.seed_world import SeedEvalWorld
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
from arbor.application.memory.bootstrap_from_inbox import BootstrapFromInbox
from arbor.application.memory.commands import ConfirmInboxItem, DismissInboxItem
from arbor.application.memory.delete_memory import DeleteMemory
from arbor.application.memory.import_jobs import RunImportJob, SubmitImportJob
from arbor.application.memory.media_to_inbox import MediaToInbox
from arbor.application.memory.process_import import ProcessImportJob
from arbor.application.memory.queries import ListMemories
from arbor.application.persona.commands import CreatePersona, PatchPersona, ReplaceGrants
from arbor.application.persona.queries import ListPersonas
from arbor.domain.errors import DomainError
from arbor.domain.identity.tenant import Role
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.env import (
    calendar_backend,
    chat_api_key,
    data_dir,
    demo_tokens_disabled,
    feishu_app_id,
    feishu_app_secret,
    feishu_redirect_uri,
    feishu_web_success_url,
    strict_tenant_membership,
    ticket_api_key,
    ticket_api_url,
    ticket_backend,
)
from arbor.env import redis_url as env_redis_url
from arbor.observability.cleanup import cleanup_expired_traces
from arbor.observability.dependency import ObservedObjectStorage
from arbor.observability.instrumentation import instrument_fastapi, instrument_httpx, instrument_psycopg
from arbor.observability.runtime import build_observability
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


def _enrich_chat_with_vision(text: str, attachments: list[dict], storage) -> str:
    from arbor.adapters.outbound.multimodal.factory import build_vision_describer
    from arbor.domain.shared.media_kinds import MediaKind, media_kind_for_filename

    describer = build_vision_describer()
    enriched = text or ""
    for att in attachments:
        uri = att.get("uri") or ""
        filename = att.get("filename") or ""
        if not uri or media_kind_for_filename(filename) is not MediaKind.IMAGE:
            continue
        blob = storage.get(uri)
        if not blob:
            continue
        parsed = describer.describe(blob, filename)
        if parsed.chunks:
            enriched = f"{enriched}\n[图片 {filename}: {parsed.chunks[0].text}]".strip()
    return enriched or text


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
    feishu: str = "stub",
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
        "feishu": feishu,
    }


def _mount_web_ui(app: FastAPI) -> None:
    dist = repo_root() / "apps" / "web" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        logging.getLogger("arbor.api").warning(
            "Web UI not built (missing %s). GET / explains how to build it.",
            index,
        )

        @app.get("/")
        def web_index_missing():
            return HTMLResponse(_WEB_UI_MISSING_HTML, status_code=503)

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


_WEB_UI_MISSING_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>Arbor — 工作台未构建</title>
</head>
<body>
  <h1>工作台还没有构建</h1>
  <p>仓库根目录执行 <code>scripts/run.sh</code> 或 <code>scripts/run.ps1</code>，会先构建 <code>apps/web/dist</code>。</p>
  <p>开发模式：API 8000 + <code>cd apps/web && npm run dev</code> 打开 http://localhost:5173</p>
</body>
</html>
"""


def _reject_oversize(data: bytes, limit: int) -> None:
    from arbor.adapters.inbound.http.chat import reject_oversize

    reject_oversize(data, limit)


def _build_calendar_stack() -> tuple[object, FeishuClient | None, FileFeishuCredentialStore]:
    """Return calendar tool, optional Feishu client, and credential store."""
    credentials = FileFeishuCredentialStore(data_dir() / "feishu_credentials")
    backend = calendar_backend()
    app_id = feishu_app_id()
    app_secret = feishu_app_secret()
    use_feishu = backend == "feishu" or (backend == "auto" and app_id and app_secret)
    if use_feishu and app_id and app_secret:
        client = FeishuClient(app_id=app_id, app_secret=app_secret)
        return FeishuCalendarTool(client, credentials), client, credentials
    return StubCalendarTool(), None, credentials


def _build_ticket_tool() -> object:
    backend = ticket_backend()
    url = ticket_api_url()
    use_http = backend == "http" or (backend == "auto" and url)
    if use_http and url:
        return HttpTicketTool(api_url=url, api_key=ticket_api_key())
    return StubTicketTool()


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
    observability = build_observability()
    instrument_httpx()
    instrument_psycopg()
    if isinstance(llm, DeepSeekChatLLM):
        llm.observability = observability
    if isinstance(reasoner, DeepSeekReasoner):
        reasoner.observability = observability
    decision_traces = None
    if database_url:
        from arbor.adapters.outbound.postgres import PostgresSession

        session = PostgresSession.connect(database_url, embed=resolved_embed, observability=observability)
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
        decision_traces = PgDecisionTraceRepository(session.conn)
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
        decision_traces = InMemoryDecisionTraceRepository(stores)
        tenants = InMemoryTenantRepository(stores)
        users = InMemoryUserRepository(stores)
    ensure_demo_member(tenants, users)
    static_tokens = {} if demo_tokens_disabled() else TOKENS
    if session is not None:
        import_jobs = PgImportJobRepository(session.conn)
        eval_runs = PgEvalRunRepository(session.conn)
        auth_sessions = PgAuthSessionStore(session.conn, static_tokens)
    else:
        import_jobs = InMemoryImportJobRepository()
        eval_runs = InMemoryEvalRunRepository()
        auth_sessions = InMemoryAuthSessionStore(static_tokens)
    ids = SeqIdGenerator(start=_highest_seq_id(session) if session is not None else 0)
    record_audit = RecordAudit(logs=audit_logs, ids=ids, clock=FixedClock())
    storage = ObservedObjectStorage(
        build_object_storage(session=session, stores=stores),
        observability,
    )
    calendar_tool, feishu_client, feishu_credentials = _build_calendar_stack()
    ticket_tool = _build_ticket_tool()
    vision_enrich = (
        (lambda text, attachments: _enrich_chat_with_vision(text, attachments, storage))
        if chat_api_key()
        else None
    )
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
        storage=storage,
        vision_enrich=vision_enrich,
        calendar_tool=calendar_tool,
        ticket_tool=ticket_tool,
        observability=observability,
        decision_traces=decision_traces,
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
        observability=observability,
    )
    dismiss = DismissInboxItem(
        personas=personas,
        inbox=inbox,
        auth=AuthorizationPolicy(),
        observability=observability,
    )
    delete_memory = DeleteMemory(
        personas=personas,
        memories=memories,
        vectors=vectors,
        auth=AuthorizationPolicy(),
        storage=storage,
        observability=observability,
    )
    bootstrap_inbox = BootstrapFromInbox(
        personas=personas,
        inbox=inbox,
        confirm=confirm,
        auth=AuthorizationPolicy(),
        observability=observability,
    )
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
    get_chat_attachment = GetChatAttachment(
        personas=personas, threads=threads, storage=storage, auth=AuthorizationPolicy()
    )
    media_to_inbox = MediaToInbox(
        personas=personas,
        inbox=inbox,
        ids=ids,
        auth=AuthorizationPolicy(),
        reasoner=reasoner or ScriptedReasoner(),
        memories=memories,
        parse_media=parse_media_bytes,
        observability=observability,
    )
    process_import = ProcessImportJob(media_to_inbox=media_to_inbox)
    run_import = RunImportJob(
        import_jobs=import_jobs,
        storage=storage,
        process_import=process_import,
        observability=observability,
    )
    submit_import = SubmitImportJob(
        personas=personas,
        storage=storage,
        import_jobs=import_jobs,
        ids=ids,
        auth=AuthorizationPolicy(),
        audit=record_audit,
        observability=observability,
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

    def run_generation_eval(*, strategy: str, suite_version: str) -> dict:
        from arbor.adapters.inbound.eval_runner import run_generation

        if not chat_api_key():
            raise DomainError("VALIDATION_ERROR", "DEEPSEEK_API_KEY required for generation eval")
        suite_dir = ROOT / "eval" / "fixtures" / "suite-v1"
        return run_generation(strategy=strategy, suite_dir=suite_dir, backend=eval_backend)

    start_eval = StartEvalRun(
        run_retrieval=run_retrieval,
        run_generation=run_generation_eval,
        ids=ids,
        observability=observability,
    )
    def _eval_fixture_path(suite_version: str) -> Path:
        if suite_version != "v1":
            raise DomainError("VALIDATION_ERROR", f"unsupported suite {suite_version}")
        return ROOT / "eval" / "fixtures" / "suite-v1" / "world.json"

    seed_eval_world = SeedEvalWorld(
        fixture_path_for=_eval_fixture_path,
        pg_clear=lambda session, tenant_ids: __import__(
            "arbor.adapters.outbound.postgres.world", fromlist=["clear_tenant_scope"]
        ).clear_tenant_scope(session, tenant_ids),
        pg_load=lambda session, path: session.load_world(path),
        mem_clear=lambda stores, tenant_ids: __import__(
            "arbor.adapters.outbound.postgres.world", fromlist=["clear_inmemory_tenant_scope"]
        ).clear_inmemory_tenant_scope(stores, tenant_ids),
        mem_load=lambda path, stores: load_world(path, stores),
    )

    def _summary_for_persona(tenant: TenantId, persona: PersonaId) -> str:
        if hasattr(threads, "summary_for"):
            return threads.summary_for(persona)
        listed = threads.list(tenant, persona)
        for thread in listed:
            if thread.summary:
                return thread.summary
        return ""

    def run_persona_retrieval_eval_fn(
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        strategy: str,
    ) -> dict:
        from arbor.application.evaluation.persona_cases import build_persona_eval_cases
        from arbor.application.evaluation.persona_eval import run_persona_retrieval_eval

        persona = personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        tenant_memories: list = []
        memory_catalog: list[dict] = []
        for listed in personas.list(tenant_id):
            active = memories.list_active(tenant_id, listed.id)
            tenant_memories.extend(active)
            for item in active:
                memory_catalog.append(
                    {
                        "id": item.id.value,
                        "tenant_id": item.tenant_id.value,
                        "status": item.status.value,
                    }
                )
        ev_nodes = events.list_nodes(tenant_id, persona_id)
        cases = build_persona_eval_cases(
            tenant_id=tenant_id,
            persona_id=persona_id,
            user_id=user_id.value,
            memories=tenant_memories,
            events=ev_nodes,
        )
        if not cases:
            raise DomainError("VALIDATION_ERROR", "not enough memories or events for persona eval")
        return run_persona_retrieval_eval(
            tenant_id=tenant_id,
            persona_id=persona_id,
            strategy=strategy,
            cases=cases,
            list_active=memories.list_active,
            list_events=events.list_nodes,
            list_edges=events.list_edges,
            summary_for=lambda p: _summary_for_persona(tenant_id, p),
            vector_search=vectors.search,
            embed=resolved_embed.embed,
            lexical_search=getattr(vectors, "lexical_search", None),
            memory_catalog=memory_catalog,
        )

    start_persona_eval = StartPersonaEvalRun(
        run_persona_retrieval=run_persona_retrieval_eval_fn,
        ids=ids,
        observability=observability,
    )

    from arbor.adapters.inbound.http.register_agent import AgentHttpDeps, register_agent_routes
    from arbor.adapters.outbound.inmemory_agent import (
        InMemoryAgentRunRepository,
        InMemoryAgentStepRepository,
        InMemoryAgentStores,
        InMemoryApprovalRepository,
        InMemoryToolExecutionRepository,
        SyncAgentJobQueue,
    )
    from arbor.application.agent.advance_run import AdvanceAgentRun
    from arbor.application.agent.approve_step import ApproveAgentStep, RejectAgentStep
    from arbor.application.agent.cancel_run import CancelAgentRun, GetAgentRun
    from arbor.application.agent.employee_templates import default_employee_templates
    from arbor.application.agent.start_run import StartAgentRun
    from arbor.application.agent.tool_executor import build_default_tool_registry, ToolExecutor

    if session is not None:
        agent_runs = session.agent_runs
        agent_steps = session.agent_steps
        agent_approvals = session.approvals
        tool_executions = session.tool_executions
    else:
        agent_stores = InMemoryAgentStores()
        agent_runs = InMemoryAgentRunRepository(agent_stores)
        agent_steps = InMemoryAgentStepRepository(agent_stores)
        agent_approvals = InMemoryApprovalRepository(agent_stores)
        tool_executions = InMemoryToolExecutionRepository(agent_stores)

    tool_registry = build_default_tool_registry()
    tool_executor = ToolExecutor(
        registry=tool_registry,
        tool_executions=tool_executions,
        calendar_tool=calendar_tool,
        ticket_tool=ticket_tool,
        observability=observability,
    )
    advance_agent_run = AdvanceAgentRun(
        personas=personas,
        runs=agent_runs,
        steps=agent_steps,
        approvals=agent_approvals,
        memories=memories,
        events=events,
        auth=AuthorizationPolicy(),
        ids=ids,
        vector_search=vectors.search,
        embed=resolved_embed.embed,
        tool_executor=tool_executor,
        observability=observability,
        lexical_search=getattr(vectors, "lexical_search", None),
    )
    agent_job_queue = SyncAgentJobQueue(advance_agent_run)
    employee_definitions = default_employee_templates()
    start_agent_run = StartAgentRun(
        personas=personas,
        runs=agent_runs,
        auth=AuthorizationPolicy(),
        ids=ids,
        employee_definitions=employee_definitions,
        job_queue=agent_job_queue,
        observability=observability,
    )
    approve_agent_step = ApproveAgentStep(
        runs=agent_runs,
        approvals=agent_approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
        advance=advance_agent_run,
    )
    reject_agent_step = RejectAgentStep(
        runs=agent_runs,
        approvals=agent_approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
    )
    cancel_agent_run = CancelAgentRun(runs=agent_runs, personas=personas, auth=AuthorizationPolicy())
    get_agent_run = GetAgentRun(
        runs=agent_runs,
        steps=agent_steps,
        personas=personas,
        auth=AuthorizationPolicy(),
    )

    def resolve_tenant(user: dict, x_tenant_id: str | None) -> TenantId:
        raw = (x_tenant_id or user.get("tenant_id") or "").strip()
        if not raw:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant_id = TenantId(raw)
        if strict_tenant_membership():
            tenant = tenants.get(tenant_id)
            if tenant is None:
                raise DomainError("NOT_FOUND", "not found")
            if tenant.member(UserId(user["user_id"])) is None:
                raise DomainError("FORBIDDEN_WORKSPACE", "not a member")
        return tenant_id

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup_expired_traces(decision_traces, storage)
        pool = None
        if redis_url:
            from arq.connections import create_pool

            pool = await create_pool(arq_redis_settings(redis_url))
            job_queue_holder.use_arq(ArqJobQueue(pool, observability=observability))
            app.state.arq_pool = pool
        yield
        if pool is not None:
            await pool.close()

    app = FastAPI(lifespan=lifespan)
    register_observability_middleware(app, observability)
    instrument_fastapi(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("ARBOR_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    limiter = InMemoryRateLimiter(limit=rate_limit_per_window, window_seconds=rate_window_seconds)

    @app.middleware("http")
    async def pg_tenant_rls(request: Request, call_next):
        if session is not None and request.headers.get("x-tenant-id"):
            from arbor.adapters.outbound.postgres.sql import set_app_tenant

            tenant_id = request.headers.get("x-tenant-id")
            conn, borrowed = session.checkout()
            try:
                with conn.transaction():
                    set_app_tenant(conn, tenant_id, local=True)
                    return await call_next(request)
            finally:
                session.checkin(conn, borrowed)
        return await call_next(request)

    @app.middleware("http")
    async def enforce_rate_limit(request: Request, call_next):
        if request.url.path.startswith("/v1"):
            key = request.headers.get("authorization") or "anon"
            try:
                limiter.check(key)
            except DomainError as exc:
                if exc.code == "RATE_LIMITED":
                    observability.increment("arbor_rate_limit_rejections_total")
                    observability.event("rate_limit.rejected", scope="v1")
                    return error_response(exc.code, str(exc), 429)
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
    app.state.observability = observability
    app.state.runtime = _runtime_info(
        llm=send.llm,
        database_url=database_url,
        embed=resolved_embed,
        object_store=object_store_label(storage),
        job_queue="redis" if redis_url else "sync",
        feishu="feishu" if feishu_client is not None else "stub",
    )
    app.state.auth_sessions = auth_sessions

    @app.exception_handler(DomainError)
    async def domain_error(_, exc: DomainError):
        status = 400
        if exc.code == "UNAUTHENTICATED":
            status = 401
        elif exc.code.startswith("FORBIDDEN"):
            status = 403
            observability.increment("arbor_permission_denials_total", error_code=exc.code)
        elif exc.code == "NOT_FOUND":
            status = 404
        elif exc.code in {"CONFLICT_INBOX_STATE", "PERSONA_TENANT_MISMATCH"}:
            status = 409
        elif exc.code == "RATE_LIMITED":
            status = 429
        elif exc.code == "UPSTREAM_UNAVAILABLE":
            status = 503
        return error_response(exc.code, str(exc), status)

    @app.exception_handler(DeepSeekUnavailable)
    async def deepseek_error(_, exc: DeepSeekUnavailable):
        return error_response("UPSTREAM_UNAVAILABLE", "chat model unavailable", 503)

    @app.exception_handler(EmbeddingUnavailable)
    async def embedding_error(_, exc: EmbeddingUnavailable):
        return error_response("UPSTREAM_UNAVAILABLE", "embedding model unavailable", 503)

    def current_user(authorization: str | None):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise DomainError("UNAUTHENTICATED", "missing bearer")
        token = authorization.split(" ", 1)[1]
        user = app.state.auth_sessions.get_profile(token)
        if not user:
            raise DomainError("UNAUTHENTICATED", "bad token")
        return user

    def workspace_admin_for(user: dict, tenant_id: str) -> bool:
        tenant = tenants.get(TenantId(tenant_id))
        if tenant is None:
            return False
        member = tenant.member(UserId(user["user_id"]))
        if member is not None and member.role in {Role.OWNER, Role.ADMIN}:
            return True
        if strict_tenant_membership():
            return False
        if user["role"] in {"owner", "admin"} and user.get("tenant_id") == tenant_id:
            return True
        return False

    register_eval_routes(
        app,
        EvalHttpDeps(
            eval_runs=eval_runs,
            start_eval=start_eval,
            start_persona_eval=start_persona_eval,
            seed_eval_world=seed_eval_world,
            personas=personas,
            session=session,
            stores=stores,
            current_user=current_user,
            workspace_admin_for=workspace_admin_for,
            resolve_tenant=resolve_tenant,
        ),
    )
    if feishu_client is not None:
        register_feishu_routes(
            app,
            FeishuHttpDeps(
                client=feishu_client,
                credentials=feishu_credentials,
                redirect_uri=feishu_redirect_uri(),
                success_url=feishu_web_success_url(),
                current_user=current_user,
            ),
        )

    register_auth_routes(
        app,
        AuthHttpDeps(
            users=users,
            tenants=tenants,
            list_tenants=list_tenants,
            authenticate_user=authenticate_user,
            profile_for_demo_email=profile_for_demo_email,
            demo_password_ok=demo_password_ok,
            current_user=current_user,
        ),
    )
    register_tenant_routes(
        app,
        TenantHttpDeps(
            list_tenants=list_tenants,
            create_tenant=create_tenant,
            delete_tenant=delete_tenant,
            list_members=list_members,
            add_member=add_member,
            patch_member=patch_member,
            current_user=current_user,
        ),
    )
    register_persona_routes(
        app,
        PersonaHttpDeps(
            personas=personas,
            memories=memories,
            inbox=inbox,
            events=events,
            import_jobs=import_jobs,
            job_queue_holder=job_queue_holder,
            list_personas=list_personas,
            create_persona=create_persona,
            patch_persona=patch_persona,
            replace_grants=replace_grants,
            list_memories=list_memories,
            delete_memory=delete_memory,
            submit_import=submit_import,
            bootstrap_inbox=bootstrap_inbox,
            confirm=confirm,
            dismiss=dismiss,
            get_tree=get_tree,
            get_card=get_card,
            max_upload_bytes=max_upload_bytes,
            current_user=current_user,
            workspace_admin_for=workspace_admin_for,
            resolve_tenant=resolve_tenant,
            threads=threads,
        ),
    )
    register_thread_routes(
        app,
        ThreadHttpDeps(
            personas=personas,
            threads=threads,
            memories=memories,
            storage=storage,
            send=send,
            media_to_inbox=media_to_inbox,
            create_thread=create_thread,
            list_threads=list_threads,
            list_messages=list_messages,
            export_thread=export_thread,
            get_chat_attachment=get_chat_attachment,
            max_upload_bytes=max_upload_bytes,
            current_user=current_user,
            resolve_tenant=resolve_tenant,
        ),
    )
    register_tools_routes(
        app,
        ToolsHttpDeps(
            personas=personas,
            ticket_tool=ticket_tool,
            calendar_tool=calendar_tool,
            auth=AuthorizationPolicy(),
            current_user=current_user,
            resolve_tenant=resolve_tenant,
        ),
    )
    register_audit_routes(
        app,
        AuditHttpDeps(
            list_audit_logs=list_audit_logs,
            current_user=current_user,
            workspace_admin_for=workspace_admin_for,
        ),
    )
    register_agent_routes(
        app,
        AgentHttpDeps(
            start_run=start_agent_run,
            get_run=get_agent_run,
            cancel_run=cancel_agent_run,
            approve_step=approve_agent_step,
            reject_step=reject_agent_step,
            approvals=agent_approvals,
            personas=personas,
            current_user=current_user,
            workspace_admin_for=workspace_admin_for,
        ),
    )
    object_store_backend = object_store_label(storage)
    register_observability_routes(
        app,
        ObservabilityHttpDeps(
            observability=observability,
            runtime=app.state.runtime,
            database_url=database_url,
            redis_url=redis_url or env_redis_url() or None,
            object_store_backend=object_store_backend,
            decision_traces=decision_traces,
            inbox=inbox,
            import_jobs=import_jobs,
            storage=storage,
            debug_web_url=os.environ.get("ARBOR_WEB_URL", "http://localhost:5173"),
            current_user=current_user,
            workspace_admin_for=workspace_admin_for,
            record_audit=record_audit,
        ),
    )

    _mount_web_ui(app)
    return app


def create_app_from_env() -> FastAPI:
    import logging

    import arbor.env as env
    from arbor.env import database_url as env_database_url
    from arbor.env import job_queue_backend
    from arbor.env import redis_url as env_redis_url

    llm = None
    reasoner = None
    if env.chat_api_key():
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
