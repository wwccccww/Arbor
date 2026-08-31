"""Published procedural memory lifecycle and agent write guards."""

from __future__ import annotations

from arbor.domain.memory.memory import MemoryClass, MemoryItem


def is_procedural_draft(item: MemoryItem) -> bool:
    if item.memory_class != MemoryClass.PROCEDURAL:
        return False
    source = item.source or {}
    return bool(source.get("draft"))


def is_procedural_memory_searchable(item: MemoryItem, *, pinned_version: str | None = None) -> bool:
    if item.memory_class != MemoryClass.PROCEDURAL:
        return True
    source = item.source or {}
    if source.get("draft"):
        return False
    if source.get("superseded"):
        return False
    version = str(source.get("version") or "").strip()
    if pinned_version:
        return version == pinned_version
    return bool(source.get("published"))


def agent_may_write_procedural(payload: dict) -> bool:
    if str(payload.get("memory_class") or "") != MemoryClass.PROCEDURAL.value:
        return True
    return not payload.get("source_run_id")
