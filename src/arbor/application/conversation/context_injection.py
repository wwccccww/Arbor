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


_TABOO_HINTS = ("香菜", "点餐", "吃", "饮食", "diet", "food", "cilantro", "spice", "辣", "meal", "order", "restrict")
_LOCATION_HINTS = ("住", "reside", "live", "区", "district", "address", "home", "where", " reside")


def select_profile_fields(query: str, profile: dict) -> dict:
    """Inject only profile fields plausibly relevant to the query (precision)."""
    if not profile:
        return {}
    lowered = (query or "").lower()
    selected: dict = {}
    if profile.get("display_name"):
        selected["display_name"] = profile["display_name"]
    taboos = profile.get("taboos")
    if taboos and any(hint in query or hint in lowered for hint in _TABOO_HINTS):
        selected["taboos"] = list(taboos)
    one_liner = profile.get("one_liner")
    if one_liner and any(hint in query or hint in lowered for hint in _LOCATION_HINTS):
        selected["one_liner"] = one_liner
    if profile.get("avatar") and not selected.get("one_liner"):
        selected["avatar"] = profile["avatar"]
    return selected
