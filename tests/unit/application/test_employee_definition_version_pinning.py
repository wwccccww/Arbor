from __future__ import annotations

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    InMemoryPersonaRepository,
    InMemoryStores,
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
from arbor.application.agent.employee_templates import LINXIA_PERSONA_ID, default_employee_templates
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _minimal_stack(employee_definitions):
    stores = InMemoryStores()
    load_world(ROOT / "eval/fixtures/suite-v1/world.json", stores)
    personas = InMemoryPersonaRepository(stores)
    persona = personas.get(TENANT, LINXIA_PERSONA_ID)
    if persona is not None:
        persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))
    agent_stores = InMemoryAgentStores()
    runs = InMemoryAgentRunRepository(agent_stores)
    from arbor.adapters.outbound.inmemory import (
        FixtureEmbeddingClient,
        InMemoryEventGraphRepository,
        InMemoryMemoryRepository,
        InMemoryVectorIndex,
    )

    memories = InMemoryMemoryRepository(stores)
    events = InMemoryEventGraphRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    embed = FixtureEmbeddingClient()
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
        embed=embed.embed,
        tool_executor=executor,
    )
    queue = SyncAgentJobQueue(advance)
    start = StartAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=700),
        employee_definitions=employee_definitions,
        job_queue=queue,
    )
    return runs, start


def test_running_run_keeps_pinned_employee_definition_after_new_publish():
    employee_definitions = default_employee_templates()
    runs, start = _minimal_stack(employee_definitions)
    run = start(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA_PERSONA_ID,
        goal="登记工单",
        enqueue=False,
    )
    assert run.employee_definition_version == "1.0"
    assert run.max_steps == 8

    employee_definitions.register(
        DigitalEmployeeDefinition(
            persona_id=LINXIA_PERSONA_ID,
            version="2.0",
            role="customer_service",
            goals=["resolve incidents"],
            skills=["policy_lookup"],
            knowledge_scopes=["semantic_memory"],
            tool_policy={"allowed_tools": ["calendar"]},
            approval_policy={"ticket.create": True},
            run_budget_policy={"max_steps": 2, "token_budget": 8000},
            evaluation_suite="agent-v1",
            release_status=EmployeeReleaseStatus.PUBLISHED,
        )
    )

    pinned = runs.get(TENANT, run.id)
    assert pinned is not None
    assert pinned.employee_definition_version == "1.0"
    assert pinned.max_steps == 8

    fresh = start(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA_PERSONA_ID,
        goal="新 Run 使用新版本",
        enqueue=False,
    )
    assert fresh.employee_definition_version == "2.0"
    assert fresh.max_steps == 2
