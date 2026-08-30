from __future__ import annotations

import json
from pathlib import Path

from arbor.application.agent.approve_step import ApproveAgentStep
from arbor.application.agent.start_run import StartAgentRun
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def run_agent_smoke(
    *,
    fixture_path: Path,
    start_run: StartAgentRun,
    approve_step: ApproveAgentStep,
    personas,
    runs,
) -> dict:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    results: list[dict] = []
    for case in payload.get("cases") or []:
        tenant_id = TenantId(str(case["tenant_id"]))
        persona_id = PersonaId(str(case["persona_id"]))
        user_id = UserId(str(case["user_id"]))
        persona = personas.get(tenant_id, persona_id)
        if persona is not None:
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

        run = start_run(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            goal=str(case.get("goal") or ""),
            plan_script=list(case.get("plan_script") or []),
            enqueue=True,
        )
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
            approve_step(
                tenant_id=tenant_id,
                user_id=user_id,
                approval_id=str(approval_id),
            )
            run = runs.get(tenant_id, run.id)
        expect_status = str(case.get("expect_final_status") or "completed")
        ok = run is not None and run.status.value == expect_status
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
    return {
        "suite_version": payload.get("suite_version"),
        "task_success_rate": success / total if total else 0.0,
        "cases": results,
    }
