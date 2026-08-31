from __future__ import annotations

from datetime import UTC, datetime

from arbor.application.memory.validity import is_memory_expired, is_memory_searchable
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _item(valid_until: str | None = None) -> MemoryItem:
    source = {"valid_until": valid_until} if valid_until else None
    return MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000501"),
        tenant_id=TENANT,
        persona_id=LINXIA,
        text="测试有效期",
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
        source=source,
    )


def test_expired_memory_not_searchable():
    past = datetime(2020, 1, 1, tzinfo=UTC)
    item = _item("2020-06-01T00:00:00Z")
    assert is_memory_expired(item, now=past.replace(year=2021))
    assert not is_memory_searchable(item, now=datetime(2021, 1, 1, tzinfo=UTC))


def test_active_memory_without_expiry_is_searchable():
    item = _item()
    assert not is_memory_expired(item)
    assert is_memory_searchable(item)
