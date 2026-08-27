"""Heuristic conflict linking for inbox extracts against active memories."""

from __future__ import annotations

from arbor.domain.memory.memory import MemoryItem
from arbor.domain.shared.ids import MemoryId

_POLARITY_PAIRS: tuple[tuple[str, str], ...] = (
    ("喜欢", "讨厌"),
    ("爱", "恨"),
    ("可以", "不能"),
    ("能", "不能"),
    ("会", "不会"),
    ("讨厌", "接受"),
    ("讨厌", "喜欢"),
    ("不能", "可以"),
)

_TOPIC_SKIP = frozenset({"林夏"})


def _strip_polarity(text: str) -> str:
    work = (text or "").strip()
    for left, right in _POLARITY_PAIRS:
        work = work.replace(left, "").replace(right, "")
    for skip in _TOPIC_SKIP:
        work = work.replace(skip, "")
    return work


def _topic_overlap(proposed: str, existing: str) -> bool:
    left = _strip_polarity(proposed)
    right = _strip_polarity(existing)
    if not left or not right:
        return False
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    for size in range(len(shorter), 1, -1):
        for index in range(len(shorter) - size + 1):
            token = shorter[index : index + size]
            if token in longer:
                return True
    return False


def texts_conflict(proposed: str, existing: str) -> bool:
    new = (proposed or "").strip()
    old = (existing or "").strip()
    if not new or not old:
        return False
    for left, right in _POLARITY_PAIRS:
        new_left, new_right = left in new, right in new
        old_left, old_right = left in old, right in old
        if ((new_left and old_right) or (new_right and old_left)) and _topic_overlap(new, old):
            return True
    return False


def find_conflicting_memory(proposed_text: str, memories: list[MemoryItem]) -> MemoryId | None:
    prop = (proposed_text or "").strip()
    if not prop:
        return None
    for item in memories:
        if item.text and texts_conflict(prop, item.text):
            return item.id
    return None


def enrich_inbox_extract(extracted: dict, memories: list[MemoryItem]) -> dict:
    """Attach conflicts_with when extract or heuristics indicate supersede."""
    if not extracted or not (extracted.get("text") or "").strip():
        return extracted
    raw = extracted.get("conflicts_with")
    if raw:
        mid = MemoryId(str(raw))
        if any(item.id == mid for item in memories):
            extracted["kind"] = "conflict"
            extracted["conflicts_with"] = mid.value
        return extracted
    target = find_conflicting_memory(str(extracted.get("text") or ""), memories)
    if target is not None:
        extracted["kind"] = "conflict"
        extracted["conflicts_with"] = target.value
    return extracted
