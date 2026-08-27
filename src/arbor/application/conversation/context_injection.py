from __future__ import annotations

from arbor.domain.memory.memory import MemoryItem


def memory_hit_payload(
    item: MemoryItem,
    *,
    source: str = "",
    score: float | None = None,
) -> dict:
    payload = {
        "id": item.id.value,
        "text": item.text or "",
        "type": item.type.value,
    }
    if source:
        payload["source"] = source
    if score is not None:
        payload["score"] = round(score, 4)
    if item.event_id:
        payload["event_id"] = item.event_id.value
    return payload


def detect_context_conflicts(profile: dict, memory_hits: list[MemoryItem]) -> list[str]:
    """Flag duplicate polarities in injected memories."""
    notes: list[str] = []
    polar_pairs = [("喜欢", "讨厌"), ("爱", "恨")]
    texts = [(hit.id.value, hit.text or "") for hit in memory_hits]
    for left, right in polar_pairs:
        left_ids = [mid for mid, text in texts if left in text]
        right_ids = [mid for mid, text in texts if right in text]
        if left_ids and right_ids:
            notes.append(f"polarity_pair:{left}:{right}")
    return notes
