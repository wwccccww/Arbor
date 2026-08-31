from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class ApprovalStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTING = "executing"
    EXECUTED = "executed"


@dataclass
class ApprovalRequest:
    id: str
    tenant_id: TenantId
    run_id: str
    step_id: str
    persona_id: PersonaId
    requested_by: UserId
    tool_name: str
    arguments: dict
    reason: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PROPOSED
    approved_by: UserId | None = None
    modified_arguments: dict | None = None
    expires_at: str | None = None
    created_at: str = ""
    resolved_at: str | None = None

    def approve(self, approver: UserId, modified_arguments: dict | None = None) -> None:
        if self.status != ApprovalStatus.PROPOSED:
            raise DomainError("APPROVAL_NOT_PENDING", "approval is not pending")
        self.status = ApprovalStatus.APPROVED
        self.approved_by = approver
        if modified_arguments is not None:
            self.modified_arguments = modified_arguments

    def reject(self, approver: UserId) -> None:
        if self.status != ApprovalStatus.PROPOSED:
            raise DomainError("APPROVAL_NOT_PENDING", "approval is not pending")
        self.status = ApprovalStatus.REJECTED
        self.approved_by = approver

    def effective_arguments(self) -> dict:
        if self.modified_arguments is not None:
            return dict(self.modified_arguments)
        return dict(self.arguments)
