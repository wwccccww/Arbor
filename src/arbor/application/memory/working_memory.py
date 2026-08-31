"""Run-scoped working memory lifecycle helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus
from arbor.env import working_memory_max_items


def _parse_iso(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def working_memory_run_id(item: MemoryItem) -> str | None:
    if item.memory_class != MemoryClass.WORKING:
        return None
    source = item.source or {}
    run_id = source.get("run_id")
    return str(run_id) if run_id else None


def is_working_memory_expired(item: MemoryItem, *, now: datetime | None = None) -> bool:
    if item.memory_class != MemoryClass.WORKING:
        return False
    source = item.source or {}
    expires_at = source.get("expires_at")
    if expires_at:
        end = _parse_iso(str(expires_at))
        if end is None:
            return False
        current = now or datetime.now(UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return current > end
    ttl_raw = source.get("ttl_seconds")
    created_raw = source.get("created_at")
    if ttl_raw is None or not created_raw:
        return False
    try:
        ttl = int(ttl_raw)
    except (TypeError, ValueError):
        return False
    created = _parse_iso(str(created_raw))
    if created is None:
        return False
    current = now or datetime.now(UTC)
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return current > created + timedelta(seconds=max(0, ttl))


def is_working_memory_for_run(item: MemoryItem, run_id: str | None) -> bool:
    if item.memory_class != MemoryClass.WORKING:
        return True
    if not run_id:
        return False
    bound = working_memory_run_id(item)
    return bound is not None and bound == run_id


def is_working_memory_searchable(
    item: MemoryItem,
    *,
    run_id: str | None = None,
    now: datetime | None = None,
) -> bool:
    if item.memory_class != MemoryClass.WORKING:
        return True
    if not is_working_memory_for_run(item, run_id):
        return False
    return not is_working_memory_expired(item, now=now)


def count_working_memory_for_run(memories, tenant_id, persona_id, run_id: str) -> int:
    total = 0
    for item in memories.list_active(tenant_id, persona_id):
        if item.memory_class != MemoryClass.WORKING:
            continue
        if working_memory_run_id(item) == run_id:
            total += 1
    return total


def enforce_working_memory_capacity(memories, tenant_id, persona_id, run_id: str) -> None:
    limit = working_memory_max_items()
    if count_working_memory_for_run(memories, tenant_id, persona_id, run_id) >= limit:
        raise DomainError(
            "WORKING_MEMORY_CAPACITY",
            f"working memory limit {limit} reached for run",
        )


def working_memory_may_enter_inbox(item: MemoryItem) -> bool:
    """Only summarized episodic candidates may enter Inbox — not raw working notes."""
    if item.memory_class != MemoryClass.WORKING:
        return True
    source = item.source or {}
    return bool(source.get("inbox_candidate"))


def clear_working_memory_for_run(memories, tenant_id, persona_id, run_id: str) -> int:
    cleared = 0
    for item in memories.list_active(tenant_id, persona_id):
        if item.memory_class != MemoryClass.WORKING:
            continue
        if working_memory_run_id(item) != run_id:
            continue
        item.status = MemoryStatus.DELETED
        memories.save(item)
        cleared += 1
    return cleared
