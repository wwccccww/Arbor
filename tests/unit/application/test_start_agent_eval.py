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
from arbor.adapters.outbound.postgres.eval_runs import InMemoryEvalRunRepository
from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.application.agent.approve_step import ApproveAgentStep, RejectAgentStep
from arbor.application.agent.employee_templates import default_employee_templates
from arbor.application.agent.resume_run import ResumeAgentRun
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry
from arbor.application.evaluation.start_agent_eval import StartAgentEvalRun
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _stack():
    stores = InMemoryStores()
    load_world(ROOT / "eval/fixtures/suite-v1/world.json", stores)
    personas = InMemoryPersonaRepository(stores)
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
    start = StartAgentRun(
        personas=personas,
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=300),
        employee_definitions=default_employee_templates(),
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
    persona = personas.get(TENANT, LINXIA)
    if persona is not None:
        persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))
    return personas, runs, start, approve, reject, resume


def test_start_agent_eval_persists_eval_run():
    personas, runs, start, approve, reject, resume = _stack()
    eval_runs = InMemoryEvalRunRepository()
    runner = StartAgentEvalRun(
        start_run=start,
        approve_step=approve,
        reject_step=reject,
        personas=personas,
        runs=runs,
        resume_run=resume,
        eval_runs=eval_runs,
        ids=SeqIdGenerator(start=400),
    )
    report = runner(workspace_admin=True, tenant_id=TENANT.value)
    assert report.get("eval_run_id")
    saved = eval_runs.get(TENANT.value, report["eval_run_id"])
    assert saved is not None
    assert saved["mode"] == "agent"
    assert saved["strategy"] == "agent-smoke"
    assert "task_success_rate" in saved["metrics"]
    assert "avg_latency_ms" in saved["metrics"]
