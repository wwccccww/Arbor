from __future__ import annotations

from pathlib import Path

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
from arbor.adapters.outbound.tools.eval_ticket import EvalTicketTool
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.approve_step import ApproveAgentStep, RejectAgentStep
from arbor.application.agent.employee_templates import default_employee_templates
from arbor.application.agent.resume_run import ResumeAgentRun
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import (
    ToolExecutor,
    build_default_tool_registry,
    register_mcp_stub_tools,
)
from arbor.domain.persona.authorization import AuthorizationPolicy


def build_agent_eval_stack(
    *,
    id_start: int = 100,
    with_mcp: bool = True,
    use_employee_templates: bool = True,
) -> dict:
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
    mcp_stub = default_mcp_stub() if with_mcp else None
    if mcp_stub is not None:
        register_mcp_stub_tools(registry, mcp_stub)
    ticket_def = registry.get("ticket.create")
    if ticket_def is not None:
        ticket_def.timeout_ms = 100
    eval_ticket = EvalTicketTool()
    executor = ToolExecutor(
        registry=registry,
        tool_executions=tool_executions,
        ticket_tool=eval_ticket,
        mcp_transport=McpJsonRpcTransport(mcp_stub) if mcp_stub is not None else None,
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
    employee_definitions = default_employee_templates() if use_employee_templates else None
    start = StartAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=id_start),
        employee_definitions=employee_definitions,
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
    return {
        "personas": personas,
        "runs": runs,
        "start_run": start,
        "approve_step": approve,
        "reject_step": reject,
        "resume_run": resume,
        "eval_ticket_tool": eval_ticket,
        "flaky_ticket_tool": eval_ticket,
        "counting_ticket_tool": eval_ticket,
    }


def agent_fixture_path() -> Path:
    return ROOT / "eval" / "fixtures" / "agent-v1" / "cases.json"
