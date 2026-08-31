from __future__ import annotations

import pytest

from arbor.application.agent.employee_commands import PublishEmployeeDefinition
from arbor.application.agent.employee_templates import (
    DEMO_TENANT,
    LINXIA_PERSONA_ID,
    InMemoryEmployeeDefinitions,
)
from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy
from arbor.domain.shared.ids import UserId


def test_publish_blocked_without_eval_gate():
    store = InMemoryEmployeeDefinitions()
    store.create_draft(
        DEMO_TENANT,
        DigitalEmployeeDefinition(
            tenant_id=DEMO_TENANT,
            persona_id=LINXIA_PERSONA_ID,
            version="2.0-draft",
            role="customer_service",
            release_status=EmployeeReleaseStatus.DRAFT,
        ),
    )
    publish = PublishEmployeeDefinition(
        personas=_FakePersonas(),
        employee_definitions=store,
        auth=AuthorizationPolicy(),
    )
    with pytest.raises(DomainError) as exc:
        publish(
            tenant_id=DEMO_TENANT,
            user_id=UserId("0a000000-0000-4000-a000-000000000002"),
            persona_id=LINXIA_PERSONA_ID,
            version="2.0-draft",
            workspace_admin=True,
        )
    assert exc.value.code == "EMPLOYEE_EVAL_GATE"


class _FakePersonas:
    def get(self, tenant_id, persona_id):
        from types import SimpleNamespace

        from arbor.domain.persona.authorization import Capability, Grant

        return SimpleNamespace(
            grants=[Grant(user_id=UserId("0a000000-0000-4000-a000-000000000002"), capabilities=[Capability.CHAT, Capability.ADMIN])]
        )
