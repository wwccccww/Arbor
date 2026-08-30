from __future__ import annotations

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack, agent_fixture_path
from arbor.application.evaluation.agent_runner import run_agent_smoke


def test_agent_smoke_ticket_approval_flow():
    stack = build_agent_eval_stack(id_start=100)
    report = run_agent_smoke(
        fixture_path=agent_fixture_path(),
        start_run=stack["start_run"],
        approve_step=stack["approve_step"],
        reject_step=stack["reject_step"],
        resume_run=stack["resume_run"],
        personas=stack["personas"],
        runs=stack["runs"],
        flaky_ticket_tool=stack["flaky_ticket_tool"],
        counting_ticket_tool=stack["counting_ticket_tool"],
    )
    assert report["task_success_rate"] == 1.0
    assert report["duplicate_side_effect_rate"] == 0.0
