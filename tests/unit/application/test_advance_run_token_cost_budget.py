from __future__ import annotations

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.application.agent.employee_templates import DEMO_TENANT, LINXIA_PERSONA_ID
from arbor.domain.shared.ids import UserId


def test_advance_run_stops_when_token_budget_exhausted():
    stack = build_agent_eval_stack(id_start=900, use_employee_templates=False)
    run = stack["start_run"](
        tenant_id=DEMO_TENANT,
        user_id=UserId("0a000000-0000-4000-a000-000000000002"),
        persona_id=LINXIA_PERSONA_ID,
        goal="token 预算",
        max_steps=8,
        token_budget=50,
        plan_script=[
            {
                "schema_version": 1,
                "action": "retrieve",
                "query": "政策",
                "scopes": ["semantic_memory"],
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
    final = stack["runs"].get(DEMO_TENANT, run.id)
    assert final is not None
    assert final.status.value == "failed"
    assert (final.failure or {}).get("kind") == "budget_exhausted"


def test_advance_run_stops_when_cost_budget_exhausted():
    stack = build_agent_eval_stack(id_start=910, use_employee_templates=False)
    run = stack["start_run"](
        tenant_id=DEMO_TENANT,
        user_id=UserId("0a000000-0000-4000-a000-000000000002"),
        persona_id=LINXIA_PERSONA_ID,
        goal="cost 预算",
        max_steps=8,
        cost_budget_micros=60_000,
        plan_script=[
            {
                "schema_version": 1,
                "action": "retrieve",
                "query": "政策",
                "scopes": ["semantic_memory"],
            },
            {
                "schema_version": 1,
                "action": "retrieve",
                "query": "二次",
                "scopes": ["semantic_memory"],
            },
        ],
        enqueue=True,
    )
    final = stack["runs"].get(DEMO_TENANT, run.id)
    assert final is not None
    assert final.status.value == "failed"
    assert (final.failure or {}).get("kind") == "budget_exhausted"
