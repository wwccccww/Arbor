from __future__ import annotations

import os

import pytest

from arbor.application.agent.employee_templates import DEMO_TENANT, LINXIA_PERSONA_ID
from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.shared.ids import TenantId
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT_B = TenantId("0b000000-0000-4000-b000-000000000001")


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_employee_definitions_rls_blocks_cross_tenant_list(pg):
    version = "9.7-rls-contract"
    definition = DigitalEmployeeDefinition(
        tenant_id=DEMO_TENANT,
        persona_id=LINXIA_PERSONA_ID,
        version=version,
        role="customer_service",
        goals=["rls"],
        release_status=EmployeeReleaseStatus.DRAFT,
        evaluation_suite="agent-v1",
    )
    pg.employee_definitions.create_draft(DEMO_TENANT, definition)
    cross = pg.employee_definitions.list_versions(TENANT_B, LINXIA_PERSONA_ID)
    assert cross == []
