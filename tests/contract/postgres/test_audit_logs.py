import os

import pytest

from arbor.domain.audit.log import AuditLog
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.env import database_url

pytestmark = pytest.mark.postgres


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres contract tests need DATABASE_URL")
def test_audit_logs_do_not_cross_tenant(pg):
    tenant_a = TenantId("0a000000-0000-4000-a000-000000000001")
    tenant_b = TenantId("0b000000-0000-4000-a000-000000000001")
    actor = UserId("0a000000-0000-4000-a000-000000000002")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    pg.audit_logs.append(
        AuditLog(
            id="c0000000-0000-4000-a000-000000000001",
            tenant_id=tenant_a,
            actor_user_id=actor,
            action="persona.update",
            resource_type="persona",
            resource_id=persona.value,
            persona_id=persona,
            payload={"fields": ["one_liner"]},
            created_at="2026-08-20T00:00:00+08:00",
        )
    )
    seen = pg.audit_logs.list(tenant_a)
    hidden = pg.audit_logs.list(tenant_b)
    assert [entry.action for entry in seen] == ["persona.update"]
    assert hidden == []
    filtered = pg.audit_logs.list(tenant_a, action="memory.confirm")
    assert filtered == []
