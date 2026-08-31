from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arbor.domain.shared.ids import PersonaId


class EmployeeReleaseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class DigitalEmployeeDefinition:
    """Versioned job definition bound to a persona."""

    persona_id: PersonaId
    version: str
    role: str
    goals: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    knowledge_scopes: list[str] = field(default_factory=list)
    tool_policy: dict = field(default_factory=dict)
    approval_policy: dict = field(default_factory=dict)
    memory_policy: dict = field(default_factory=dict)
    escalation_policy: dict = field(default_factory=dict)
    run_budget_policy: dict = field(default_factory=dict)
    evaluation_suite: str = "agent-v1"
    release_status: EmployeeReleaseStatus = EmployeeReleaseStatus.PUBLISHED
