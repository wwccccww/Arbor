from __future__ import annotations

import os

import pytest

from arbor.application.agent.employee_templates import DEMO_TENANT, LINXIA_PERSONA_ID
from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT_B = TenantId("0b000000-0000-4000-b000-000000000001")


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_employee_definition_not_visible_cross_tenant(pg):
    definition = DigitalEmployeeDefinition(
        tenant_id=DEMO_TENANT,
        persona_id=LINXIA_PERSONA_ID,
        version="9.9-contract",
        role="customer_service",
        goals=["contract test"],
        release_status=EmployeeReleaseStatus.DRAFT,
        evaluation_suite="agent-v1",
    )
    pg.employee_definitions.create_draft(DEMO_TENANT, definition)
    assert pg.employee_definitions.get(TENANT_B, LINXIA_PERSONA_ID, "9.9-contract") is None


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_publish_requires_eval_gate(pg):
    version = "9.8-gate-contract"
    definition = DigitalEmployeeDefinition(
        tenant_id=DEMO_TENANT,
        persona_id=LINXIA_PERSONA_ID,
        version=version,
        role="customer_service",
        goals=["gate test"],
        release_status=EmployeeReleaseStatus.DRAFT,
        evaluation_suite="agent-v1",
    )
    pg.employee_definitions.create_draft(DEMO_TENANT, definition)
    with pytest.raises(DomainError) as exc:
        pg.employee_definitions.publish(DEMO_TENANT, LINXIA_PERSONA_ID, version)
    assert exc.value.code == "EMPLOYEE_EVAL_GATE"
    pg.employee_definitions.record_eval_gate(
        DEMO_TENANT, LINXIA_PERSONA_ID, version, gate_passed=True
    )
    published = pg.employee_definitions.publish(DEMO_TENANT, LINXIA_PERSONA_ID, version)
    assert published.release_status == EmployeeReleaseStatus.PUBLISHED
