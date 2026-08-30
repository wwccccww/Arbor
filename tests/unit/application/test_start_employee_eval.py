from __future__ import annotations

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    InMemoryEventGraphRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    FixtureEmbeddingClient,
    SeqIdGenerator,
)
from arbor.adapters.outbound.inmemory_agent import (
    InMemoryAgentRunRepository,
    InMemoryAgentStores,
    InMemoryApprovalRepository,
    InMemoryAgentStepRepository,
    InMemoryToolExecutionRepository,
    SyncAgentJobQueue,
)
from arbor.adapters.outbound.postgres.eval_runs import InMemoryEvalRunRepository
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.approve_step import ApproveAgentStep, RejectAgentStep
from arbor.application.agent.employee_templates import default_employee_templates, LINXIA_PERSONA_ID
from arbor.application.agent.resume_run import ResumeAgentRun
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.application.evaluation.start_employee_eval import StartEmployeeEvalRun
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _stack():
    stores = InMemoryStores()
    load_world(ROOT / "eval/fixtures/suite-v1/world.json", stores)
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
    employee_definitions = default_employee_templates()
    start = StartAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=300),
        employee_definitions=employee_definitions,
        job_queue=queue,
    )
    approve = ApproveAgentStep(
        runs=runs,
        approvals=approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
        advance=advance,
    )
    reject = RejectAgentStep(
        runs=runs,
        approvals=approvals,
        personas=personas,
        auth=AuthorizationPolicy(),
    )
    resume = ResumeAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        job_queue=queue,
        advance=advance,
    )
    persona = personas.get(TENANT, LINXIA_PERSONA_ID)
    if persona is not None:
        persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))
    return personas, runs, start, approve, reject, resume, employee_definitions


def test_start_employee_eval_gate_passes_for_linxia():
    personas, runs, start, approve, reject, resume, employee_definitions = _stack()
    eval_runs = InMemoryEvalRunRepository()
    runner = StartEmployeeEvalRun(
        start_run=start,
        approve_step=approve,
        reject_step=reject,
        personas=personas,
        runs=runs,
        employee_definitions=employee_definitions,
        auth=AuthorizationPolicy(),
        resume_run=resume,
        eval_runs=eval_runs,
        ids=SeqIdGenerator(start=500),
    )
    report = runner(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA_PERSONA_ID,
        workspace_admin=True,
    )
    assert report["gate_passed"] is True
    assert report["evaluation_suite"] == "agent-v1"
    assert report.get("eval_run_id")
    saved = eval_runs.get(TENANT.value, report["eval_run_id"])
    assert saved is not None
    assert saved["mode"] == "employee"
    assert saved["strategy"] == "employee-gate"
    assert saved["metrics"]["gate_passed"] is True


def test_start_employee_eval_requires_admin():
    personas, runs, start, approve, reject, resume, employee_definitions = _stack()
    runner = StartEmployeeEvalRun(
        start_run=start,
        approve_step=approve,
        reject_step=reject,
        personas=personas,
        runs=runs,
        employee_definitions=employee_definitions,
        auth=AuthorizationPolicy(),
        resume_run=resume,
    )
    try:
        runner(
            tenant_id=TENANT,
            user_id=USER,
            persona_id=LINXIA_PERSONA_ID,
            workspace_admin=False,
        )
        assert False, "expected FORBIDDEN_WORKSPACE"
    except DomainError as exc:
        assert exc.code == "FORBIDDEN_WORKSPACE"
