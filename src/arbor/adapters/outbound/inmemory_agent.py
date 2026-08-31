from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.agent.approval import ApprovalRequest, ApprovalStatus
from arbor.domain.agent.run import AgentRun
from arbor.domain.agent.step import AgentStep
from arbor.domain.shared.ids import PersonaId, TenantId


@dataclass
class InMemoryAgentStores:
    runs: dict[str, AgentRun] = field(default_factory=dict)
    steps: dict[str, AgentStep] = field(default_factory=dict)
    approvals: dict[str, ApprovalRequest] = field(default_factory=dict)
    tool_executions: dict[str, dict] = field(default_factory=dict)


class InMemoryAgentRunRepository:
    def __init__(self, stores: InMemoryAgentStores) -> None:
        self.stores = stores

    def get(self, tenant_id: TenantId, run_id: str) -> AgentRun | None:
        run = self.stores.runs.get(run_id)
        if run is None or run.tenant_id != tenant_id:
            return None
        return run

    def save(self, run: AgentRun) -> None:
        self.stores.runs[run.id] = run

    def list_for_persona(
        self, tenant_id: TenantId, persona_id: PersonaId, *, limit: int = 20
    ) -> list[AgentRun]:
        items = [
            run
            for run in self.stores.runs.values()
            if run.tenant_id == tenant_id and run.persona_id == persona_id
        ]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[:limit]

    def try_advance_version(self, tenant_id: TenantId, run_id: str, expected_version: int) -> bool:
        run = self.get(tenant_id, run_id)
        if run is None or run.version != expected_version:
            return False
        run.bump_version()
        return True


class InMemoryAgentStepRepository:
    def __init__(self, stores: InMemoryAgentStores) -> None:
        self.stores = stores

    def add(self, step: AgentStep) -> None:
        self.stores.steps[step.id] = step

    def list_for_run(self, tenant_id: TenantId, run_id: str) -> list[AgentStep]:
        items = [
            step
            for step in self.stores.steps.values()
            if step.run_id == run_id and step.tenant_id == tenant_id
        ]
        return sorted(items, key=lambda s: s.sequence)

    def get(self, tenant_id: TenantId, step_id: str) -> AgentStep | None:
        step = self.stores.steps.get(step_id)
        if step is None or step.tenant_id != tenant_id:
            return None
        return step


class InMemoryApprovalRepository:
    def __init__(self, stores: InMemoryAgentStores) -> None:
        self.stores = stores

    def add(self, approval: ApprovalRequest) -> None:
        self.stores.approvals[approval.id] = approval

    def get(self, tenant_id: TenantId, approval_id: str) -> ApprovalRequest | None:
        approval = self.stores.approvals.get(approval_id)
        if approval is None or approval.tenant_id != tenant_id:
            return None
        return approval

    def save(self, approval: ApprovalRequest) -> None:
        self.stores.approvals[approval.id] = approval

    def list_pending(self, tenant_id: TenantId, *, limit: int = 50) -> list[ApprovalRequest]:
        items = [
            approval
            for approval in self.stores.approvals.values()
            if approval.tenant_id == tenant_id and approval.status == ApprovalStatus.PROPOSED
        ]
        items.sort(key=lambda a: a.created_at, reverse=True)
        return items[:limit]


class InMemoryToolExecutionRepository:
    def __init__(self, stores: InMemoryAgentStores) -> None:
        self.stores = stores

    def _key(self, tenant_id: TenantId, tool_name: str, idempotency_key: str) -> str:
        return f"{tenant_id.value}:{tool_name}:{idempotency_key}"

    def reserve(
        self,
        tenant_id: TenantId,
        tool_name: str,
        idempotency_key: str,
        *,
        run_id: str | None,
        step_id: str | None,
        arguments: dict,
    ) -> dict | None:
        key = self._key(tenant_id, tool_name, idempotency_key)
        existing = self.stores.tool_executions.get(key)
        if existing is not None:
            return existing
        record = {
            "tenant_id": tenant_id.value,
            "tool_name": tool_name,
            "idempotency_key": idempotency_key,
            "run_id": run_id,
            "step_id": step_id,
            "arguments": dict(arguments),
            "status": "pending",
            "result": None,
        }
        self.stores.tool_executions[key] = record
        return None

    def complete(self, tenant_id: TenantId, tool_name: str, idempotency_key: str, result: dict) -> None:
        key = self._key(tenant_id, tool_name, idempotency_key)
        record = self.stores.tool_executions.get(key)
        if record is None:
            return
        record["status"] = "completed"
        record["result"] = dict(result)

    def fail(self, tenant_id: TenantId, tool_name: str, idempotency_key: str, error_kind: str) -> None:
        key = self._key(tenant_id, tool_name, idempotency_key)
        record = self.stores.tool_executions.get(key)
        if record is None:
            return
        record["status"] = "failed"
        record["error_kind"] = error_kind


class SyncAgentJobQueue:
    """Inline agent advancement for tests and demo without Redis."""

    def __init__(self, advance) -> None:
        self._advance = advance
        self._tenant_id: TenantId | None = None
        self._user_id = None

    def bind_actor(self, tenant_id: TenantId, user_id) -> None:
        self._tenant_id = tenant_id
        self._user_id = user_id

    @property
    def is_async(self) -> bool:
        return False

    def enqueue_run(self, tenant_id: TenantId, run_id: str, expected_version: int) -> None:
        if self._tenant_id is None or self._user_id is None:
            return
        guard = 0
        while guard < 16:
            guard += 1
            run = self._advance(
                tenant_id=self._tenant_id,
                user_id=self._user_id,
                run_id=run_id,
                expected_version=expected_version,
                enqueue_next=False,
            )
            if run.is_terminal() or run.status.value == "waiting_approval":
                break
            expected_version = run.version
