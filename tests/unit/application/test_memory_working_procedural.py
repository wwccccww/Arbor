from __future__ import annotations

from datetime import UTC, datetime

import pytest

from arbor.application.memory.procedural_memory import (
    agent_may_write_procedural,
    is_procedural_memory_searchable,
)
from arbor.application.memory.validity import is_memory_searchable
from arbor.application.memory.working_memory import (
    clear_working_memory_for_run,
    is_working_memory_expired,
    is_working_memory_for_run,
)
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _working(**source) -> MemoryItem:
    return MemoryItem(
        id=MemoryId("mem-working-test"),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text="working note",
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.WORKING,
        source=source,
    )


def test_working_memory_requires_matching_run():
    item = _working(run_id="run-a", expires_at="2099-01-01T00:00:00Z")
    assert is_working_memory_for_run(item, "run-a")
    assert not is_working_memory_for_run(item, "run-b")
    assert is_memory_searchable(item, run_id="run-a")
    assert not is_memory_searchable(item, run_id="run-b")
    assert not is_memory_searchable(item)


def test_working_memory_expires():
    item = _working(run_id="run-a", expires_at="2020-01-01T00:00:00Z")
    assert is_working_memory_expired(item, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert not is_memory_searchable(item, run_id="run-a", now=datetime(2026, 1, 1, tzinfo=UTC))


def test_procedural_draft_and_pinning():
    draft = MemoryItem(
        id=MemoryId("proc-draft"),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text="draft",
        memory_class=MemoryClass.PROCEDURAL,
        source={"draft": True, "version": "v2"},
    )
    published = MemoryItem(
        id=MemoryId("proc-pub"),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text="published",
        memory_class=MemoryClass.PROCEDURAL,
        source={"published": True, "version": "v1"},
    )
    assert not is_procedural_memory_searchable(draft)
    assert is_procedural_memory_searchable(published)
    assert is_procedural_memory_searchable(published, pinned_version="v1")
    assert not is_procedural_memory_searchable(published, pinned_version="v2")


def test_working_memory_capacity_limit():
    from arbor.adapters.outbound.inmemory import InMemoryMemoryRepository, InMemoryStores
    from arbor.application.memory.working_memory import enforce_working_memory_capacity
    from arbor.domain.errors import DomainError

    stores = InMemoryStores()
    memories = InMemoryMemoryRepository(stores)
    run_id = "run-capacity"
    for i in range(32):
        item = _working(run_id=run_id, expires_at="2099-01-01T00:00:00Z")
        item.id = MemoryId(f"mem-w-{i:03d}")
        memories.save(item)
    with pytest.raises(DomainError) as exc:
        enforce_working_memory_capacity(memories, TENANT, PERSONA, run_id)
    assert exc.value.code == "WORKING_MEMORY_CAPACITY"


def test_agent_cannot_write_procedural_from_run():
    payload = {
        "memory_class": "procedural",
        "source_run_id": "run-123",
        "text": "override SOP",
    }
    assert not agent_may_write_procedural(payload)


class _Memories:
    def __init__(self, items: list[MemoryItem]) -> None:
        self._items = {item.id.value: item for item in items}

    def list_active(self, tenant_id, persona_id):
        return [
            item
            for item in self._items.values()
            if item.tenant_id == tenant_id
            and item.persona_id == persona_id
            and item.status == MemoryStatus.ACTIVE
        ]

    def get(self, tenant_id, memory_id):
        item = self._items.get(memory_id.value if hasattr(memory_id, "value") else str(memory_id))
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def save(self, item):
        self._items[item.id.value] = item


def test_clear_working_memory_for_run():
    item = _working(run_id="run-clear")
    memories = _Memories([item])
    cleared = clear_working_memory_for_run(memories, TENANT, PERSONA, "run-clear")
    assert cleared == 1
    stored = memories.get(TENANT, item.id)
    assert stored is not None
    assert stored.status == MemoryStatus.DELETED
