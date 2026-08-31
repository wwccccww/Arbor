from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.agent.run import AgentRunStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class UpdateAgentRunGoal:
    """Record goal revision; clear scripted plan so stale side effects do not continue."""

    def __init__(self, *, runs, personas, auth: AuthorizationPolicy) -> None:
        self.runs = runs
        self.personas = personas
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        run_id: str,
        new_goal: str,
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
            raise DomainError("AGENT_RUN_TERMINAL", "cannot change goal on terminal run")

        goal_text = (new_goal or "").strip()
        if not goal_text:
            raise DomainError("VALIDATION_ERROR", "goal required")

        now = _now_iso()
        events = list(run.metadata.get("goal_events") or [])
        events.append({"from": run.goal, "to": goal_text, "at": now})
        run.metadata["goal_events"] = events
        run.metadata["goal_revision"] = int(run.metadata.get("goal_revision") or 0) + 1
        run.metadata["plan_script"] = []
        run.metadata.pop("pending_approval_id", None)
        if run.status == AgentRunStatus.WAITING_APPROVAL:
            run.status = AgentRunStatus.RUNNING
        run.goal = goal_text
        run.updated_at = now
        self.runs.save(run)
        return {
            "run_id": run.id,
            "goal": run.goal,
            "goal_revision": run.metadata["goal_revision"],
        }
