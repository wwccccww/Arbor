from __future__ import annotations

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    InMemoryEventGraphRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.adapters.outbound.inmemory_agent import (
    InMemoryAgentRunRepository,
    InMemoryAgentStores,
    SyncAgentJobQueue,
)
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.employee_templates import default_employee_templates
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT_A = TenantId("0a000000-0000-4000-a000-000000000001")
TENANT_B = TenantId("0b000000-0000-4000-b000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _agent_stack(stores: InMemoryStores):
    load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    events = InMemoryEventGraphRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    agent_stores = InMemoryAgentStores()
    runs = InMemoryAgentRunRepository(agent_stores)
    from arbor.adapters.outbound.inmemory_agent import (
        InMemoryAgentStepRepository,
        InMemoryApprovalRepository,
        InMemoryToolExecutionRepository,
    )

    steps = InMemoryAgentStepRepository(agent_stores)
    approvals = InMemoryApprovalRepository(agent_stores)
    tool_executions = InMemoryToolExecutionRepository(agent_stores)
    executor = ToolExecutor(registry=build_default_tool_registry(), tool_executions=tool_executions)
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
        embed=lambda text: [0.1, 0.2],
        tool_executor=executor,
    )
    queue = SyncAgentJobQueue(advance)
    employee_definitions = default_employee_templates()
    start = StartAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=200),
        employee_definitions=employee_definitions,
        job_queue=queue,
    )
    persona = personas.get(TENANT_A, LINXIA)
    if persona is not None:
        persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))
    return personas, runs, start


def test_agent_run_not_visible_cross_tenant():
    stores = InMemoryStores()
    _, runs, start = _agent_stack(stores)
    run = start(
        tenant_id=TENANT_A,
        user_id=USER,
        persona_id=LINXIA,
        goal="租户 A 任务",
        enqueue=False,
    )
    assert runs.get(TENANT_B, run.id) is None


def test_start_run_pins_employee_definition_version():
    stores = InMemoryStores()
    _, _, start = _agent_stack(stores)
    run = start(
        tenant_id=TENANT_A,
        user_id=USER,
        persona_id=LINXIA,
        goal="登记工单",
        enqueue=False,
    )
    assert run.employee_definition_version == "1.0"
