from __future__ import annotations

from typing import Protocol

from arbor.domain.agent.employee import DigitalEmployeeDefinition
from arbor.domain.shared.ids import PersonaId, TenantId


class EmployeeDefinitionRepository(Protocol):
    def create_draft(
        self,
        tenant_id: TenantId,
        definition: DigitalEmployeeDefinition,
    ) -> DigitalEmployeeDefinition: ...

    def get(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str | None = None,
    ) -> DigitalEmployeeDefinition | None: ...

    def list_versions(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
    ) -> list[DigitalEmployeeDefinition]: ...

    def record_eval_gate(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
        *,
        gate_passed: bool,
        report: dict | None = None,
    ) -> None: ...

    def publish(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
    ) -> DigitalEmployeeDefinition: ...

    def archive(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
    ) -> DigitalEmployeeDefinition: ...
