from __future__ import annotations

from arbor.application.evaluation.agent_eval_stack import build_agent_eval_stack
from arbor.domain.shared.ids import TenantId, UserId
from arbor.application.agent.employee_templates import LINXIA_PERSONA_ID

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def test_advance_run_stops_when_max_steps_budget_exhausted():
    stack = build_agent_eval_stack(id_start=800, use_employee_templates=False)
    start = stack["start_run"]
    runs = stack["runs"]
    run = start(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA_PERSONA_ID,
        goal="预算耗尽测试",
        max_steps=2,
        plan_script=[
            {
                "schema_version": 1,
                "action": "retrieve",
                "query": "退货政策",
                "scopes": ["semantic_memory"],
                "reason": "lookup",
            },
            {
                "schema_version": 1,
                "action": "retrieve",
                "query": "二次检索",
                "scopes": ["semantic_memory"],
                "reason": "second lookup",
            },
            {
                "schema_version": 1,
                "action": "answer",
                "text": "完成",
                "citations": [],
                "completion": True,
            },
        ],
        enqueue=True,
    )
    final = runs.get(TENANT, run.id)
    assert final is not None
    assert final.status.value == "failed"
    assert final.failure is not None
    assert final.failure.get("kind") == "budget_exhausted"
    assert final.current_step <= 2
