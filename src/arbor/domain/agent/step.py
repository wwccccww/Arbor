from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId


class StepKind(str, Enum):
    PLAN = "plan"
    RETRIEVE = "retrieve"
    TOOL = "tool"
    REFLECT = "reflect"
    ANSWER = "answer"
    HANDOFF = "handoff"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentStep:
    id: str
    run_id: str
    tenant_id: TenantId
    persona_id: PersonaId
    sequence: int
    kind: StepKind
    status: StepStatus = StepStatus.PENDING
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    observation: dict = field(default_factory=dict)
    retry_count: int = 0
    error_kind: str | None = None
    error_message: str | None = None
    trace_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.run_id:
            raise DomainError("VALIDATION_ERROR", "agent step id and run_id required")
        if self.sequence < 0:
            raise DomainError("VALIDATION_ERROR", "sequence must be non-negative")

    def mark_completed(self, output: dict, observation: dict | None = None) -> None:
        self.status = StepStatus.COMPLETED
        self.output = output
        if observation is not None:
            self.observation = observation

    def mark_failed(self, error_kind: str, error_message: str) -> None:
        self.status = StepStatus.FAILED
        self.error_kind = error_kind
        self.error_message = error_message
