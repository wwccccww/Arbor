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
from arbor.adapters.outbound.mcp.jsonrpc_transport import McpJsonRpcTransport
from arbor.adapters.outbound.mcp.stub_adapter import default_mcp_stub
from arbor.adapters.outbound.tools.flaky_ticket import FlakyTicketTool
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.approve_step import ApproveAgentStep, RejectAgentStep
from arbor.application.agent.resume_run import ResumeAgentRun
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import (
    ToolExecutor,
    build_default_tool_registry,
    register_mcp_stub_tools,
)
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
    mcp_stub = default_mcp_stub()
    register_mcp_stub_tools(registry, mcp_stub)
    ticket_def = registry.get("ticket.create")
    assert ticket_def is not None
    ticket_def.timeout_ms = 100
    flaky = FlakyTicketTool()
    executor = ToolExecutor(
        registry=registry,
        tool_executions=tool_executions,
        ticket_tool=flaky,
        mcp_transport=McpJsonRpcTransport(mcp_stub),
    )
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
    reject = RejectAgentStep(
        runs=runs,
        approvals=approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
    )
    approve = ApproveAgentStep(
        runs=runs,
        approvals=approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
        advance=advance,
    )
    resume = ResumeAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        job_queue=queue,
        advance=advance,
    )
    report = run_agent_smoke(
        fixture_path=ROOT / "eval" / "fixtures" / "agent-v1" / "cases.json",
        start_run=start,
        approve_step=approve,
        reject_step=reject,
        resume_run=resume,
        personas=personas,
        runs=runs,
        flaky_ticket_tool=flaky,
    )
    assert report["task_success_rate"] == 1.0
