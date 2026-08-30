from __future__ import annotations

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryEventGraphRepository,
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
    SyncAgentJobQueue,
)
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.approve_step import ApproveAgentStep
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.application.evaluation.agent_runner import run_agent_smoke
from arbor.domain.persona.authorization import AuthorizationPolicy


def test_agent_smoke_ticket_approval_flow():
    stores = InMemoryStores()
    load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    events = InMemoryEventGraphRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    embed = FixtureEmbeddingClient()

    agent_stores = InMemoryAgentStores()
    runs = InMemoryAgentRunRepository(agent_stores)
    steps = InMemoryAgentStepRepository(agent_stores)
    approvals = InMemoryApprovalRepository(agent_stores)
    tool_executions = InMemoryToolExecutionRepository(agent_stores)
    registry = build_default_tool_registry()
    executor = ToolExecutor(registry=registry, tool_executions=tool_executions)
    advance = AdvanceAgentRun(
        personas=personas,
        runs=runs,
        steps=steps,
        approvals=approvals,
        memories=memories,
        events=events,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(),
        vector_search=vectors.search,
        embed=embed.embed,
        tool_executor=executor,
    )
    queue = SyncAgentJobQueue(advance)
    start = StartAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=100),
        job_queue=queue,
    )
    approve = ApproveAgentStep(
        runs=runs,
        approvals=approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
        advance=advance,
    )
    report = run_agent_smoke(
        fixture_path=ROOT / "eval" / "fixtures" / "agent-v1" / "cases.json",
        start_run=start,
        approve_step=approve,
        personas=personas,
        runs=runs,
    )
    assert report["task_success_rate"] == 1.0
