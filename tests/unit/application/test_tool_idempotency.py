from __future__ import annotations

from arbor.adapters.outbound.inmemory_agent import (
    InMemoryAgentStores,
    InMemoryToolExecutionRepository,
)
from arbor.adapters.outbound.tools.counting_ticket import CountingTicketTool
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.agent.step import AgentStep, StepKind, StepStatus
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _executor(counter: CountingTicketTool) -> ToolExecutor:
    stores = InMemoryAgentStores()
    return ToolExecutor(
        registry=build_default_tool_registry(),
        tool_executions=InMemoryToolExecutionRepository(stores),
        ticket_tool=counter,
    )


def _run_and_step() -> tuple[AgentRun, AgentStep]:
    run = AgentRun(
        id="run-idem-001",
        tenant_id=TENANT,
        persona_id=PERSONA,
        requested_by=USER,
        goal="登记工单：空调故障",
        status=AgentRunStatus.RUNNING,
        max_steps=4,
        token_budget=16000,
        metadata={},
    )
    step = AgentStep(
        id="step-idem-001",
        run_id=run.id,
        tenant_id=TENANT,
        persona_id=PERSONA,
        sequence=1,
        kind=StepKind.TOOL,
        status=StepStatus.RUNNING,
        input={},
    )
    return run, step


def test_ticket_create_idempotency_prevents_duplicate_side_effects():
    counter = CountingTicketTool()
    executor = _executor(counter)
    run, step = _run_and_step()
    args = {"title": "会议室空调故障", "priority": "high"}
    first = executor.execute(
        tenant_id=TENANT,
        user_id=USER,
        run=run,
        step=step,
        tool_name="ticket.create",
        arguments=args,
        allowed_tools={"ticket", "ticket.create"},
    )
    second = executor.execute(
        tenant_id=TENANT,
        user_id=USER,
        run=run,
        step=step,
        tool_name="ticket.create",
        arguments=args,
        allowed_tools={"ticket", "ticket.create"},
    )
    assert counter.create_calls == 1
    assert first == second
    assert first["ticket_id"] == "count-001"


def test_ticket_create_distinct_steps_invoke_twice():
    counter = CountingTicketTool()
    executor = _executor(counter)
    run, step_one = _run_and_step()
    args = {"title": "会议室空调故障", "priority": "high"}
    executor.execute(
        tenant_id=TENANT,
        user_id=USER,
        run=run,
        step=step_one,
        tool_name="ticket.create",
        arguments=args,
        allowed_tools={"ticket", "ticket.create"},
    )
    step_two = AgentStep(
        id="step-idem-002",
        run_id=run.id,
        tenant_id=TENANT,
        persona_id=PERSONA,
        sequence=2,
        kind=StepKind.TOOL,
        status=StepStatus.RUNNING,
        input={},
    )
    executor.execute(
        tenant_id=TENANT,
        user_id=USER,
        run=run,
        step=step_two,
        tool_name="ticket.create",
        arguments={"title": "另一条工单", "priority": "normal"},
        allowed_tools={"ticket", "ticket.create"},
    )
    assert counter.create_calls == 2
