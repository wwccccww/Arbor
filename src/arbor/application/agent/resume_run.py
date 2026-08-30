from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.agent.run import AgentRunStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ResumeAgentRun:
    """Resume a non-terminal run or re-enqueue advancement after worker interruption."""

    def __init__(
        self,
        *,
        personas,
        runs,
        auth: AuthorizationPolicy,
        job_queue=None,
        advance=None,
    ) -> None:
        self.personas = personas
        self.runs = runs
        self.auth = auth
        self.job_queue = job_queue
        self.advance = advance

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        run_id: str,
        enqueue: bool = True,
    ) -> dict:
        run = self.runs.get(tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "agent run not found")
        persona = self.personas.get(tenant_id, run.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        if run.is_terminal():
            raise DomainError("AGENT_RUN_TERMINAL", "cannot resume terminal run")
        if run.status == AgentRunStatus.WAITING_APPROVAL:
            raise DomainError("AGENT_RUN_NOT_WAITING", "run is waiting for approval, not resumable")

        if run.status == AgentRunStatus.FAILED:
            run.status = AgentRunStatus.RETRYING
            run.failure = None
            run.finished_at = None
        elif run.status == AgentRunStatus.PENDING:
            run.status = AgentRunStatus.PENDING
        else:
            run.status = AgentRunStatus.RUNNING
        run.updated_at = _now_iso()
        run.bump_version()
        self.runs.save(run)

        if enqueue and self.job_queue is not None:
            if hasattr(self.job_queue, "bind_actor"):
                self.job_queue.bind_actor(tenant_id, user_id)
            self.job_queue.enqueue_run(tenant_id, run.id, run.version)
        elif self.advance is not None:
            self.advance(
                tenant_id=tenant_id,
                user_id=user_id,
                run_id=run.id,
                expected_version=run.version,
            )
            run = self.runs.get(tenant_id, run.id) or run

        return {"id": run.id, "status": run.status.value, "version": run.version}
