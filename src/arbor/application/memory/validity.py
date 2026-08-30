"""Memory validity checks for retrieval and context injection."""

from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.memory.memory import MemoryItem


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


def is_memory_expired(item: MemoryItem, *, now: datetime | None = None) -> bool:
    source = item.source or {}
    valid_until = source.get("valid_until")
    if not valid_until:
        return False
    end = _parse_iso(str(valid_until))
    if end is None:
        return False
    current = now or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return current > end


def is_memory_searchable(item: MemoryItem, *, now: datetime | None = None) -> bool:
    return item.is_searchable() and not is_memory_expired(item, now=now)
