from __future__ import annotations

from datetime import UTC, datetime

from arbor.application.memory.decay import is_episodic_decayed
from arbor.application.memory.validity import is_memory_searchable
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _episodic(recorded_at: str, decay_days: int = 30) -> MemoryItem:
    return MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000502"),
        tenant_id=TENANT,
        persona_id=LINXIA,
        text="古老情景",
        type=MemoryType.EPISODE_SUMMARY,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.EPISODIC,
        source={"recorded_at": recorded_at, "decay_after_days": decay_days},
    )


def test_episodic_decayed_after_window():
    item = _episodic("2019-01-01T00:00:00Z", 30)
    now = datetime(2020, 6, 1, tzinfo=UTC)
    assert is_episodic_decayed(item, now=now)
    assert not is_memory_searchable(item, now=now)


def test_recent_episodic_not_decayed():
    item = _episodic("2025-01-01T00:00:00Z", 30)
    now = datetime(2025, 1, 15, tzinfo=UTC)
    assert not is_episodic_decayed(item, now=now)
    assert is_memory_searchable(item, now=now)
