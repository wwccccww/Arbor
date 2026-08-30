from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CancelAgentRun:
    def __init__(self, *, runs, personas, auth: AuthorizationPolicy) -> None:
        self.runs = runs
        self.personas = personas
        self.auth = auth

    def __call__(self, *, tenant_id: TenantId, user_id: UserId, run_id: str) -> dict:
        run = self.runs.get(tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "agent run not found")
        persona = self.personas.get(tenant_id, run.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        if run.is_terminal():
            return {"id": run.id, "status": run.status.value}
        run.mark_cancelled()
        run.updated_at = _now_iso()
        self.runs.save(run)
        return {"id": run.id, "status": run.status.value}


class GetAgentRun:
    def __init__(self, *, runs, steps, personas, auth: AuthorizationPolicy, lineage=None) -> None:
        self.runs = runs
        self.steps = steps
        self.personas = personas
        self.auth = auth
        self.lineage = lineage

    def __call__(self, *, tenant_id: TenantId, user_id: UserId, run_id: str) -> dict:
        run = self.runs.get(tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "agent run not found")
        persona = self.personas.get(tenant_id, run.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        steps = self.steps.list_for_run(tenant_id, run_id)
        payload = {
            "run": _run_dict(run),
            "steps": [_step_dict(step) for step in steps],
        }
        if self.lineage is not None:
            payload["lineage"] = self.lineage.list_for_run(tenant_id, run_id)
        return payload


def _run_dict(run) -> dict:
    return {
        "id": run.id,
        "tenant_id": run.tenant_id.value,
        "persona_id": run.persona_id.value,
        "thread_id": run.thread_id.value if run.thread_id else None,
        "goal": run.goal,
        "status": run.status.value,
        "current_step": run.current_step,
        "max_steps": run.max_steps,
        "token_budget": run.token_budget,
        "consumed_tokens": run.consumed_tokens,
        "version": run.version,
        "employee_definition_version": run.employee_definition_version,
        "final_output": run.final_output,
        "failure": run.failure,
        "metadata": dict(run.metadata),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "finished_at": run.finished_at,
    }


def _step_dict(step) -> dict:
    return {
        "id": step.id,
        "run_id": step.run_id,
        "sequence": step.sequence,
        "kind": step.kind.value,
        "status": step.status.value,
        "input": dict(step.input),
        "output": dict(step.output),
        "observation": dict(step.observation),
        "retry_count": step.retry_count,
        "error_kind": step.error_kind,
        "error_message": step.error_message,
        "started_at": step.started_at,
        "finished_at": step.finished_at,
    }
