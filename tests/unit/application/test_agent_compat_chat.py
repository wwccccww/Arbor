from __future__ import annotations

from unittest.mock import patch

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryThreadRepository,
    InMemoryVectorIndex,
    ScriptedLLM,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.adapters.outbound.inmemory_agent import (
    InMemoryAgentRunRepository,
    InMemoryAgentStores,
    SyncAgentJobQueue,
)
from arbor.application.agent.compat_chat import AgentCompatRecorder
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.conversation.send_message import SendMessage
from arbor.domain.conversation.thread import Thread
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import USER, load_mini

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
THREAD = ThreadId("0a000000-0000-4000-a000-000000000020")


def _send_with_compat(stores: InMemoryStores) -> tuple[SendMessage, InMemoryAgentRunRepository]:
    memories = InMemoryMemoryRepository(stores)
    agent_stores = InMemoryAgentStores()
    runs = InMemoryAgentRunRepository(agent_stores)
    from arbor.adapters.outbound.inmemory_agent import (
        InMemoryAgentStepRepository,
        InMemoryApprovalRepository,
        InMemoryToolExecutionRepository,
    )
    from arbor.application.agent.advance_run import AdvanceAgentRun
    from arbor.application.agent.tool_executor import ToolExecutor, build_default_tool_registry

    steps = InMemoryAgentStepRepository(agent_stores)
    approvals = InMemoryApprovalRepository(agent_stores)
    tool_executions = InMemoryToolExecutionRepository(agent_stores)
    executor = ToolExecutor(registry=build_default_tool_registry(), tool_executions=tool_executions)
    advance = AdvanceAgentRun(
        personas=InMemoryPersonaRepository(stores),
        runs=runs,
        steps=steps,
        approvals=approvals,
        memories=memories,
        events=InMemoryEventGraphRepository(stores),
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=500),
        vector_search=InMemoryVectorIndex(stores, memories).search,
        embed=FixtureEmbeddingClient().embed,
        tool_executor=executor,
    )
    queue = SyncAgentJobQueue(advance)
    start = StartAgentRun(
        personas=InMemoryPersonaRepository(stores),
        runs=runs,
        auth=AuthorizationPolicy(),
        ids=SeqIdGenerator(start=100),
        job_queue=queue,
    )
    compat = AgentCompatRecorder(start_run=start, runs=runs, job_queue=queue)
    send = SendMessage(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        threads=InMemoryThreadRepository(stores),
        events=InMemoryEventGraphRepository(stores),
        inbox=InMemoryInboxRepository(stores),
        vectors=InMemoryVectorIndex(stores, memories),
        llm=ScriptedLLM(),
        reasoner=ScriptedReasoner(),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        agent_compat=compat,
    )
    return send, runs


def test_send_message_compat_records_max_steps_one_agent_run():
    stores = InMemoryStores()
    load_mini(stores)
    stores.threads[THREAD.value] = Thread(
        id=THREAD,
        tenant_id=TENANT,
        persona_id=LINXIA,
        summary="compat thread",
    )
    send, runs = _send_with_compat(stores)
    with patch("arbor.application.conversation.send_message.agent_compat_chat", return_value=True):
        out = send(
            tenant_id=TENANT,
            user_id=USER,
            persona_id=LINXIA,
            thread_id=THREAD,
            text="林夏喜欢什么？",
            capabilities=list(Capability),
        )
    agent_run_id = out.get("agent_run_id")
    assert agent_run_id
    run = runs.get(TENANT, agent_run_id)
    assert run is not None
    assert run.max_steps == 1
    assert run.metadata.get("compat_mode") is True
    assert run.status.value == "completed"
    assert isinstance(run.metadata.get("retrieval_meta"), dict)
    assert out["retrieval_meta"] == run.metadata["retrieval_meta"]
    assert out.get("decision_trace") is not None


def test_send_message_compat_disabled_skips_agent_run():
    stores = InMemoryStores()
    load_mini(stores)
    stores.threads[THREAD.value] = Thread(
        id=THREAD,
        tenant_id=TENANT,
        persona_id=LINXIA,
        summary="compat thread",
    )
    send, _runs = _send_with_compat(stores)
    with patch("arbor.application.conversation.send_message.agent_compat_chat", return_value=False):
        out = send(
            tenant_id=TENANT,
            user_id=USER,
            persona_id=LINXIA,
            thread_id=THREAD,
            text="林夏喜欢什么？",
            capabilities=list(Capability),
        )
    assert out.get("agent_run_id") is None
