"""Contract: memory_class column round-trips through Postgres."""

from __future__ import annotations

import os

import pytest

from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_memory_class_episodic_searchable(pg):
    memory_id = MemoryId("0a000000-0000-4000-a000-000000000999")
    item = MemoryItem(
        id=memory_id,
        tenant_id=TENANT,
        persona_id=LINXIA,
        text="情景记忆：会议室空调维修经历",
        type=MemoryType.EPISODE_SUMMARY,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.EPISODIC,
        source={"recorded_at": "2025-06-01T00:00:00Z"},
    )
    pg.memories.save(item)
    pg.vectors.upsert(TENANT, LINXIA, memory_id, fixture_embed(item.text), item.status)

    loaded = pg.memories.get(TENANT, memory_id)
    assert loaded is not None
    assert loaded.memory_class == MemoryClass.EPISODIC

    hits = pg.vectors.search(TENANT, LINXIA, fixture_embed("空调维修"), 5)
    assert any(hit[0].id == memory_id for hit in hits)
