"""Helpers for episodic memory consolidation metadata and grouping."""

from __future__ import annotations

from arbor.application.memory.conflict_detection import _topic_overlap
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryType


def is_consolidation(item: MemoryItem) -> bool:
    source = item.source or {}
    return bool(source.get("consolidation"))


def derived_from_ids(item: MemoryItem) -> list[str]:
    source = item.source or {}
    raw = source.get("derived_from") or []
    return [str(value) for value in raw]


def consolidations_deriving_from(memories: list[MemoryItem], memory_id: str) -> list[MemoryItem]:
    hits: list[MemoryItem] = []
    for item in memories:
        if not is_consolidation(item):
            continue
        if memory_id in derived_from_ids(item):
            hits.append(item)
    return hits


def group_similar_episodes(items: list[MemoryItem], *, min_overlap: bool = True) -> list[list[MemoryItem]]:
    pool = [
        item
        for item in items
        if item.is_searchable() and not is_consolidation(item)
        and (item.memory_class == MemoryClass.EPISODIC or item.type == MemoryType.EPISODE_SUMMARY)
    ]
    groups: list[list[MemoryItem]] = []
    used: set[str] = set()
    for index, item in enumerate(pool):
        if item.id.value in used:
            continue
        group = [item]
        used.add(item.id.value)
        for other in pool[index + 1 :]:
            if other.id.value in used:
                continue
            overlaps = any(_topic_overlap(anchor.text, other.text) for anchor in group)
            if min_overlap and overlaps:
                group.append(other)
                used.add(other.id.value)
        if len(group) >= 2:
            groups.append(group)
    return groups


def build_consolidation_text(group: list[MemoryItem]) -> str:
    parts = [f"{idx + 1}) {item.text.strip()}" for idx, item in enumerate(group)]
    return "合并情景记忆：" + "；".join(parts)
