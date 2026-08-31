from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    HANDED_OFF = "handed_off"


_TERMINAL = frozenset(
    {
        AgentRunStatus.COMPLETED,
        AgentRunStatus.FAILED,
        AgentRunStatus.CANCELLED,
        AgentRunStatus.HANDED_OFF,
    }
)


@dataclass
class AgentRun:
    id: str
    tenant_id: TenantId
    persona_id: PersonaId
    requested_by: UserId
    goal: str
    status: AgentRunStatus = AgentRunStatus.PENDING
    thread_id: ThreadId | None = None
    current_step: int = 0
    max_steps: int = 8
    token_budget: int = 16000
    consumed_tokens: int = 0
    cost_budget_micros: int = 0
    consumed_cost_micros: int = 0
    version: int = 1
    employee_definition_version: str | None = None
    final_output: dict | None = None
    failure: dict | None = None
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    finished_at: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise DomainError("VALIDATION_ERROR", "agent run id required")
        if not self.tenant_id or not self.persona_id:
            raise DomainError("VALIDATION_ERROR", "agent run requires tenant and persona")
        if self.max_steps < 1:
            raise DomainError("VALIDATION_ERROR", "max_steps must be positive")

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL

    def can_advance(self) -> bool:
        return self.status in {
            AgentRunStatus.PENDING,
            AgentRunStatus.RUNNING,
            AgentRunStatus.RETRYING,
        }

    def budget_exhausted(self) -> bool:
        if self.current_step >= self.max_steps:
            return True
        if self.consumed_tokens >= self.token_budget:
            return True
        return self.cost_budget_micros > 0 and self.consumed_cost_micros >= self.cost_budget_micros

    def mark_running(self) -> None:
        if self.is_terminal():
            raise DomainError("AGENT_RUN_TERMINAL", "cannot run terminal agent run")
        self.status = AgentRunStatus.RUNNING

    def mark_waiting_approval(self) -> None:
        self.status = AgentRunStatus.WAITING_APPROVAL

    def mark_completed(self, output: dict) -> None:
        self.status = AgentRunStatus.COMPLETED
        self.final_output = output
        self.finished_at = self.updated_at

    def mark_failed(self, failure: dict) -> None:
        self.status = AgentRunStatus.FAILED
        self.failure = failure
        self.finished_at = self.updated_at

    def mark_cancelled(self) -> None:
        self.status = AgentRunStatus.CANCELLED
        self.finished_at = self.updated_at

    def bump_version(self) -> int:
        self.version += 1
        return self.version
