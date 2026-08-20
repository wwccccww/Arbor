import os

import pytest

from arbor.domain.memory.memory import MemoryStatus, MemoryType
from arbor.domain.shared.ids import EventId, PersonaId, TenantId
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT_A = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
ZHOU = PersonaId("0a000000-0000-4000-a000-000000000020")
ZHOU_EVENT = EventId("0a000000-0000-4000-a000-000000000201")


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres contract tests need DATABASE_URL")
def test_memory_list_stays_in_persona(pg):
    leaked = pg.memories.list(
        TENANT_A,
        LINXIA,
        event_id=ZHOU_EVENT,
        status=MemoryStatus.ACTIVE,
    )
    assert leaked == []
    handbook = pg.memories.list(
        TENANT_A,
        ZHOU,
        memory_type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
    )
    assert handbook
    assert all(item.persona_id == ZHOU for item in handbook)
    assert all(item.tenant_id == TENANT_A for item in handbook)
