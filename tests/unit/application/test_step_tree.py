from __future__ import annotations

from arbor.application.agent.step_tree import build_agent_step_tree
from arbor.domain.agent.step import AgentStep, StepKind, StepStatus
from arbor.domain.shared.ids import PersonaId, TenantId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _step(
    *,
    sequence: int,
    kind: StepKind,
    output: dict,
    observation: dict | None = None,
) -> AgentStep:
    return AgentStep(
        id=f"step-{sequence}",
        run_id="run-1",
        tenant_id=TENANT,
        persona_id=LINXIA,
        sequence=sequence,
        kind=kind,
        status=StepStatus.COMPLETED,
        output=output,
        observation=observation or {},
    )


def test_build_agent_step_tree_nested_rag_and_tool():
    steps = [
        _step(
            sequence=1,
            kind=StepKind.RETRIEVE,
            output={
                "hit_ids": ["m1"],
                "context_manifest": {"selected_item_ids": ["m1"], "token_usage": 120},
            },
            observation={"latency_ms": 15},
        ),
        _step(
            sequence=2,
            kind=StepKind.TOOL,
            output={"tool": "ticket.create", "result": {"ticket_id": "T-1"}},
        ),
    ]
    tree = build_agent_step_tree(steps, run_goal="登记工单")
    assert tree["type"] == "run"
    assert tree["label"] == "登记工单"
    assert len(tree["children"]) == 2
    retrieve = tree["children"][0]
    assert retrieve["kind"] == "retrieve"
    assert retrieve["latency_ms"] == 15
    assert any(child["type"] == "rag" for child in retrieve["children"])
