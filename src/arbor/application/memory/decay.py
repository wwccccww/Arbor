"""Episodic memory time-based decay for retrieval filtering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryType

DEFAULT_EPISODIC_DECAY_DAYS = 180


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


def is_episodic_decayed(item: MemoryItem, *, now: datetime | None = None) -> bool:
    """Return True when an episodic item is past its decay window."""
    if item.memory_class != MemoryClass.EPISODIC and item.type != MemoryType.EPISODE_SUMMARY:
        return False
    source = item.source or {}
    if source.get("consolidation"):
        return False
    recorded_raw = source.get("recorded_at") or source.get("episode_at")
    if not recorded_raw:
        return False
    recorded = _parse_iso(str(recorded_raw))
    if recorded is None:
        return False
    decay_days = int(source.get("decay_after_days") or DEFAULT_EPISODIC_DECAY_DAYS)
    if decay_days <= 0:
        return False
    current = now or datetime.now(UTC)
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=UTC)
    return current > recorded + timedelta(days=decay_days)
