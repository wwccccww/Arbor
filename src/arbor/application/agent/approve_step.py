from __future__ import annotations

from datetime import UTC, datetime

from arbor.application.agent.advance_run import AdvanceAgentRun
from arbor.domain.agent.run import AgentRunStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ApproveAgentStep:
    def __init__(
        self,
        *,
        runs,
        approvals,
        personas,
        auth: AuthorizationPolicy,
        advance: AdvanceAgentRun,
    ) -> None:
        self.runs = runs
        self.approvals = approvals
        self.personas = personas
        self.auth = auth
        self.advance = advance

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        approval_id: str,
        modified_arguments: dict | None = None,
    ) -> dict:
        approval = self.approvals.get(tenant_id, approval_id)
        if approval is None:
            raise DomainError("NOT_FOUND", "approval not found")
        persona = self.personas.get(tenant_id, approval.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = self.auth.capabilities_for(persona, user_id)
        if Capability.ADMIN not in caps and Capability.WRITE_MEMORY not in caps:
            raise DomainError("FORBIDDEN", "approval requires admin or write_memory")

        run = self.runs.get(tenant_id, approval.run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "agent run not found")
        if run.status != AgentRunStatus.WAITING_APPROVAL:
            raise DomainError("AGENT_RUN_NOT_WAITING", "run is not waiting for approval")

        approval.approve(user_id, modified_arguments)
        approval.resolved_at = _now_iso()
        self.approvals.save(approval)

        args = approval.effective_arguments()
        step = self.advance.steps.get(tenant_id, approval.step_id)
        if step is None:
            raise DomainError("NOT_FOUND", "agent step not found")

        from arbor.application.tools.run_tools import allowed_tool_names

        allowed = allowed_tool_names(persona.tool_policy)
        result = self.advance.tool_executor.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            run=run,
            step=step,
            tool_name=approval.tool_name,
            arguments=args,
            allowed_tools=allowed,
        )
        step.output = {"tool": approval.tool_name, "result": result, "approved": True}
        step.observation = result
        step.finished_at = _now_iso()
        self.advance.steps.add(step)

        run.status = AgentRunStatus.RUNNING
        run.metadata.pop("pending_approval_id", None)
        run.metadata.setdefault("tool_results", []).append(result)
        pending = str(result.get("title") or result.get("ticket_id") or "").strip()
        if pending:
            run.metadata["pending_retrieve_query"] = f"{pending} 处理方案"
        run.updated_at = _now_iso()
        run.bump_version()
        self.runs.save(run)

        expected_version = run.version
        guard = 0
        while guard < 16:
            guard += 1
            run = self.runs.get(tenant_id, run.id)
            if run is None or run.is_terminal() or run.status == AgentRunStatus.WAITING_APPROVAL:
                break
            run = self.advance(
                tenant_id=tenant_id,
                user_id=user_id,
                run_id=run.id,
                expected_version=expected_version,
            )
            expected_version = run.version
        return {"approval_id": approval.id, "status": approval.status.value, "result": result}


class RejectAgentStep:
    def __init__(self, *, runs, approvals, personas, auth: AuthorizationPolicy) -> None:
        self.runs = runs
        self.approvals = approvals
        self.personas = personas
        self.auth = auth

    def __call__(self, *, tenant_id: TenantId, user_id: UserId, approval_id: str) -> dict:
        approval = self.approvals.get(tenant_id, approval_id)
        if approval is None:
            raise DomainError("NOT_FOUND", "approval not found")
        persona = self.personas.get(tenant_id, approval.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = self.auth.capabilities_for(persona, user_id)
        if Capability.ADMIN not in caps and Capability.WRITE_MEMORY not in caps:
            raise DomainError("FORBIDDEN", "approval requires admin or write_memory")

        approval.reject(user_id)
        approval.resolved_at = _now_iso()
        self.approvals.save(approval)

        run = self.runs.get(tenant_id, approval.run_id)
        if run is not None:
            run.mark_failed({"kind": "approval_rejected", "approval_id": approval.id})
            run.updated_at = _now_iso()
            self.runs.save(run)
        return {"approval_id": approval.id, "status": approval.status.value}
