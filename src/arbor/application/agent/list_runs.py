from __future__ import annotations

from arbor.application.agent.cancel_run import _run_dict, _step_dict
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class ListAgentRuns:
    def __init__(self, *, personas, runs, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.runs = runs
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        limit: int = 20,
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        capped = max(1, min(limit, 50))
        items = self.runs.list_for_persona(tenant_id, persona_id, limit=capped)
        return {"items": [_run_dict(run) for run in items]}


class GetAgentRunSteps:
    def __init__(self, *, runs, steps, personas, auth: AuthorizationPolicy) -> None:
        self.runs = runs
        self.steps = steps
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
        steps = self.steps.list_for_run(tenant_id, run_id)
        return {"run_id": run_id, "steps": [_step_dict(step) for step in steps]}
