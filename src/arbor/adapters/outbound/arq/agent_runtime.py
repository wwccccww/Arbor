"""Build agent runtime for API and ARQ worker."""

from __future__ import annotations

from dataclasses import dataclass

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.embedding import FixtureEmbeddingClient, embedding_client_from_env
from arbor.adapters.outbound.inmemory import (
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.adapters.outbound.inmemory_agent import (
    InMemoryAgentRunRepository,
    InMemoryAgentStepRepository,
    InMemoryAgentStores,
    InMemoryApprovalRepository,
    InMemoryToolExecutionRepository,
)
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.approve_step import ApproveAgentStep
from arbor.application.agent.extract_memory import ExtractRunMemory
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId

LINXIA_ID = "0a000000-0000-4000-a000-000000000010"
MEMBER_ID = "0a000000-0000-4000-a000-000000000003"


@dataclass
class AgentRuntime:
    advance_run: AdvanceAgentRun
    start_run: StartAgentRun
    approve_step: ApproveAgentStep
    extract_memory: ExtractRunMemory
    agent_runs: object


def build_agent_runtime(
    *,
    database_url: str | None = None,
    embed=None,
    observability: object | None = None,
    calendar_tool=None,
    ticket_tool=None,
) -> AgentRuntime:
    if embed is not None:
        resolved_embed = embed
    elif database_url:
        resolved_embed = embedding_client_from_env()
    else:
        resolved_embed = FixtureEmbeddingClient()

    if database_url:
        from arbor.adapters.outbound.postgres import PostgresSession

        session = PostgresSession.connect(database_url, embed=resolved_embed, observability=observability)
        session.migrate()
        session.seed_demo_world_if_empty()
        personas = session.personas
        memories = session.memories
        events = session.events
        vectors = session.vectors
        inbox = session.inbox
        agent_runs = session.agent_runs
        agent_steps = session.agent_steps
        approvals = session.approvals
        tool_executions = session.tool_executions
        embed_fn = session.embed.embed
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
        events = InMemoryEventGraphRepository(stores)
        vectors = InMemoryVectorIndex(stores, memories)
        inbox = InMemoryInboxRepository(stores)
        agent_stores = InMemoryAgentStores()
        agent_runs = InMemoryAgentRunRepository(agent_stores)
        agent_steps = InMemoryAgentStepRepository(agent_stores)
        approvals = InMemoryApprovalRepository(agent_stores)
        tool_executions = InMemoryToolExecutionRepository(agent_stores)
        embed_fn = resolved_embed.embed

    ids = SeqIdGenerator()
    registry = build_default_tool_registry()
    tool_executor = ToolExecutor(
        registry=registry,
        tool_executions=tool_executions,
        calendar_tool=calendar_tool,
        ticket_tool=ticket_tool,
        observability=observability,
    )
    extract_memory = ExtractRunMemory(
        personas=personas,
        inbox=inbox,
        memories=memories,
        ids=ids,
        auth=AuthorizationPolicy(),
    )
    advance_run = AdvanceAgentRun(
        personas=personas,
        runs=agent_runs,
        steps=agent_steps,
        approvals=approvals,
        memories=memories,
        events=events,
        auth=AuthorizationPolicy(),
        ids=ids,
        vector_search=vectors.search,
        embed=embed_fn,
        tool_executor=tool_executor,
        observability=observability,
        lexical_search=getattr(vectors, "lexical_search", None),
        extract_memory=extract_memory,
    )
    start_run = StartAgentRun(
        personas=personas,
        runs=agent_runs,
        auth=AuthorizationPolicy(),
        ids=ids,
        observability=observability,
    )
    approve_step = ApproveAgentStep(
        runs=agent_runs,
        approvals=approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
        advance=advance_run,
    )
    return AgentRuntime(
        advance_run=advance_run,
        start_run=start_run,
        approve_step=approve_step,
        extract_memory=extract_memory,
        agent_runs=agent_runs,
    )
