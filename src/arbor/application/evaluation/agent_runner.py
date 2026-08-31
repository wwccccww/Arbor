from __future__ import annotations

import json
from pathlib import Path

from arbor.application.agent.approve_step import ApproveAgentStep, RejectAgentStep
from arbor.application.agent.start_run import StartAgentRun
from arbor.application.tools.run_tools import allowed_tool_names
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def run_agent_smoke(
    *,
    fixture_path: Path,
    start_run: StartAgentRun,
    approve_step: ApproveAgentStep,
    reject_step: RejectAgentStep | None = None,
    resume_run=None,
    personas,
    runs,
    flaky_ticket_tool=None,
    counting_ticket_tool=None,
    persona_id: PersonaId | None = None,
    case_ids: set[str] | None = None,
    max_steps_cap: int | None = None,
) -> dict:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    results: list[dict] = []
    unauthorized = 0
    approval_bypass = 0
    duplicate_side_effects = 0
    latency_samples: list[float] = []
    cost_samples: list[int] = []

    cases = list(payload.get("cases") or [])
    if persona_id is not None:
        filtered = [c for c in cases if str(c.get("persona_id")) == persona_id.value]
        if filtered:
            cases = filtered
    if case_ids is not None:
        cases = [c for c in cases if c.get("id") in case_ids]

    for case in cases:
        tenant_id = TenantId(str(case["tenant_id"]))
        persona_id = PersonaId(str(case["persona_id"]))
        user_id = UserId(str(case["user_id"]))
        persona = personas.get(tenant_id, persona_id)
        if persona is not None:
            if case.get("strip_tools"):
                persona.tool_policy.allowed_tools = []
            else:
                allowed = list(persona.tool_policy.allowed_tools or [])
                for tool in ("ticket", "calendar"):
                    if tool not in allowed:
                        allowed.append(tool)
                persona.tool_policy.allowed_tools = allowed
            if not any(
                Capability.ADMIN in g.capabilities for g in persona.grants if g.user_id == user_id
            ):
                persona.grants.append(
                    Grant(user_id=user_id, capabilities=[Capability.ADMIN, Capability.CHAT])
                )

        ticket_calls_before = None
        if flaky_ticket_tool is not None and case.get("expect_timeout_retry"):
            ticket_calls_before = flaky_ticket_tool.create_calls
        counting_before = (
            counting_ticket_tool.create_calls
            if counting_ticket_tool is not None and case.get("expect_idempotent_side_effect")
            else None
        )

        try:
            enqueue = not case.get("simulate_worker_restart")
            run = start_run(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                goal=str(case.get("goal") or ""),
                plan_script=list(case.get("plan_script") or []),
                enqueue=enqueue,
                max_steps=int(
                    max_steps_cap if max_steps_cap is not None else int(case.get("max_steps") or 8)
                ),
            )
            if case.get("simulate_worker_restart") and resume_run is not None:
                approve_step.advance(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    run_id=run.id,
                    expected_version=run.version,
                    enqueue_next=False,
                )
                resume_run(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    run_id=run.id,
                    enqueue=True,
                )
                run = runs.get(tenant_id, run.id)
        except DomainError as exc:
            if case.get("expect_error"):
                results.append({"id": case["id"], "ok": True, "error": str(exc)})
                continue
            results.append({"id": case["id"], "ok": False, "reason": str(exc)})
            continue

        if case.get("expect_waiting_approval"):
            if run.status.value != "waiting_approval":
                results.append(
                    {
                        "id": case["id"],
                        "ok": False,
                        "reason": f"expected waiting_approval got {run.status.value}",
                    }
                )
                continue
            approval_id = run.metadata.get("pending_approval_id")
            if not approval_id:
                results.append({"id": case["id"], "ok": False, "reason": "missing approval id"})
                continue
            if case.get("expect_reject_approval") and reject_step is not None:
                reject_step(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    approval_id=str(approval_id),
                )
            else:
                approve_step(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    approval_id=str(approval_id),
                )
            run = runs.get(tenant_id, run.id)

        if case.get("replay_tool_on_last_step") and run is not None:
            tool_steps = [
                s
                for s in approve_step.advance.steps.list_for_run(tenant_id, run.id)
                if s.kind.value == "tool"
            ]
            if tool_steps:
                last = tool_steps[-1]
                tool_name = str(last.input.get("tool_name") or "")
                approve_step.advance.tool_executor.execute(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    run=run,
                    step=last,
                    tool_name=tool_name,
                    arguments=dict(last.input.get("arguments") or {}),
                    allowed_tools=allowed_tool_names(persona.tool_policy),
                )

        expect_status = str(case.get("expect_final_status") or "completed")
        ok = run is not None and run.status.value == expect_status
        if ok and case.get("expect_second_retrieval"):
            step_list = approve_step.advance.steps.list_for_run(tenant_id, run.id)
            retrieve_count = sum(1 for s in step_list if s.kind.value == "retrieve")
            ok = retrieve_count >= 2
        if case.get("expect_forbidden_tool") and run is not None and run.status.value != "failed":
            unauthorized += 1
            ok = False
        if case.get("expect_no_approval_bypass") and run is not None:
            tool_steps = [
                s
                for s in approve_step.advance.steps.list_for_run(tenant_id, run.id)
                if s.kind.value == "tool" and s.output.get("approved")
            ]
            if tool_steps and run.status.value == "completed" and case.get("expect_waiting_approval"):
                approval_bypass += 1
                ok = False
        if case.get("expect_timeout_retry") and flaky_ticket_tool is not None:
            ok = ok and flaky_ticket_tool.create_calls == ticket_calls_before + 1
        if case.get("expect_idempotent_side_effect") and counting_ticket_tool is not None:
            ok = ok and counting_ticket_tool.create_calls == counting_before + 1
            if counting_ticket_tool.create_calls > counting_before + 1:
                duplicate_side_effects += 1
                ok = False
        if run is not None:
            metrics = dict(run.metadata.get("metrics") or {})
            if metrics.get("total_latency_ms") is not None:
                latency_samples.append(float(metrics["total_latency_ms"]))
            cost_samples.append(int(run.consumed_cost_micros or 0))
        results.append(
            {
                "id": case["id"],
                "ok": ok,
                "status": run.status.value if run else None,
                "steps": run.current_step if run else 0,
            }
        )

    success = sum(1 for item in results if item.get("ok"))
    total = len(results)
    avg_latency = sum(latency_samples) / len(latency_samples) if latency_samples else 0.0
    avg_cost_micros = sum(cost_samples) / len(cost_samples) if cost_samples else 0.0
    return {
        "suite_version": payload.get("suite_version"),
        "task_success_rate": success / total if total else 0.0,
        "unauthorized_action_rate": unauthorized / total if total else 0.0,
        "approval_bypass_rate": approval_bypass / total if total else 0.0,
        "duplicate_side_effect_rate": duplicate_side_effects / total if total else 0.0,
        "avg_latency_ms": round(avg_latency, 2),
        "avg_cost_micros": round(avg_cost_micros, 2),
        "cases": results,
    }
