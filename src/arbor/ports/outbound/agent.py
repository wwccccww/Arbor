from __future__ import annotations

from typing import Protocol

from arbor.domain.agent.approval import ApprovalRequest
from arbor.domain.agent.run import AgentRun
from arbor.domain.agent.step import AgentStep
from arbor.domain.shared.ids import PersonaId, TenantId


class AgentRunRepository(Protocol):
    def get(self, tenant_id: TenantId, run_id: str) -> AgentRun | None: ...
    def save(self, run: AgentRun) -> None: ...
    def list_for_persona(
        self, tenant_id: TenantId, persona_id: PersonaId, *, limit: int = 20
    ) -> list[AgentRun]: ...
    def try_advance_version(self, tenant_id: TenantId, run_id: str, expected_version: int) -> bool: ...


class AgentStepRepository(Protocol):
    def add(self, step: AgentStep) -> None: ...
    def list_for_run(self, tenant_id: TenantId, run_id: str) -> list[AgentStep]: ...
    def get(self, tenant_id: TenantId, step_id: str) -> AgentStep | None: ...


class ApprovalRepository(Protocol):
    def add(self, approval: ApprovalRequest) -> None: ...
    def get(self, tenant_id: TenantId, approval_id: str) -> ApprovalRequest | None: ...
    def save(self, approval: ApprovalRequest) -> None: ...
    def list_pending(self, tenant_id: TenantId, *, limit: int = 50) -> list[ApprovalRequest]: ...


class ToolExecutionRepository(Protocol):
    def reserve(
        self,
        tenant_id: TenantId,
        tool_name: str,
        idempotency_key: str,
        *,
        run_id: str | None,
        step_id: str | None,
        arguments: dict,
    ) -> dict | None: ...
    def complete(self, tenant_id: TenantId, tool_name: str, idempotency_key: str, result: dict) -> None: ...
    def fail(
        self,
        tenant_id: TenantId,
        tool_name: str,
        idempotency_key: str,
        error_kind: str,
    ) -> None: ...


class AgentJobQueue(Protocol):
  @property
  def is_async(self) -> bool: ...

  def enqueue_run(self, tenant_id: TenantId, run_id: str, expected_version: int) -> None: ...
