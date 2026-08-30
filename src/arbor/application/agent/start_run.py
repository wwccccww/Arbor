from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId
from arbor.observability.context import current_request_context, merge_request_context


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class StartAgentRun:
    def __init__(
        self,
        *,
        personas,
        runs,
        auth: AuthorizationPolicy,
        ids,
        employee_definitions=None,
        job_queue=None,
        observability=None,
    ) -> None:
        self.personas = personas
        self.runs = runs
        self.auth = auth
        self.ids = ids
        self.employee_definitions = employee_definitions
        self.job_queue = job_queue
        self.observability = observability

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        goal: str,
        thread_id: ThreadId | None = None,
        max_steps: int = 8,
        token_budget: int = 16000,
        cost_budget_micros: int = 0,
        employee_definition_version: str | None = None,
        plan_script: list[dict] | None = None,
        enqueue: bool = True,
    ) -> AgentRun:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        goal_text = (goal or "").strip()
        if not goal_text:
            raise DomainError("VALIDATION_ERROR", "goal required")

        definition_version = employee_definition_version
        budget_policy: dict = {}
        if self.employee_definitions is not None:
            definition = self.employee_definitions.get(
                persona_id, version=employee_definition_version
            )
            if definition is not None:
                definition_version = definition.version
                budget_policy = dict(definition.run_budget_policy or {})

        now = _now_iso()
        request_id = self.ids.new_id()
        ctx = current_request_context()
        if ctx is not None and ctx.request_id:
            request_id = ctx.request_id
        metadata: dict = {"plan_script": plan_script or [], "request_id": request_id}
        if self.employee_definitions is not None:
            definition = self.employee_definitions.get(persona_id, version=employee_definition_version)
            if definition is not None and definition.evaluation_suite:
                metadata["evaluation_suite"] = definition.evaluation_suite
        run = AgentRun(
            id=self.ids.new_id(),
            tenant_id=tenant_id,
            persona_id=persona_id,
            requested_by=user_id,
            goal=goal_text,
            status=AgentRunStatus.PENDING,
            thread_id=thread_id,
            max_steps=int(budget_policy.get("max_steps") or max_steps),
            token_budget=int(budget_policy.get("token_budget") or token_budget),
            cost_budget_micros=int(budget_policy.get("cost_budget_micros") or cost_budget_micros),
            employee_definition_version=definition_version,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        self.runs.save(run)
        if enqueue and self.job_queue is not None:
            if hasattr(self.job_queue, "bind_actor"):
                self.job_queue.bind_actor(tenant_id, user_id)
            self.job_queue.enqueue_run(tenant_id, run.id, run.version)
        return run
