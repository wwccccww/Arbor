from __future__ import annotations

import copy
from typing import Any

from arbor.observability.sampling import encrypt_payload, should_capture_content


def build_encrypted_content_sample(
    *,
    tenant_id: str,
    user_message: str,
    model_response: str,
    prompt_slots: dict[str, Any] | None,
    reasoning_content: str | None,
) -> tuple[str | None, bool]:
    if not should_capture_content(tenant_id=tenant_id):
        return None, False
    payload = {
        "user_message": user_message,
        "model_response": model_response,
        "prompt_slots": _capture_prompt_slots(prompt_slots or {}),
        "reasoning_content": reasoning_content,
    }
    encrypted = encrypt_payload(payload)
    return encrypted, encrypted is not None


def _capture_prompt_slots(slots: dict[str, Any]) -> dict[str, Any]:
    captured = copy.deepcopy(slots)
    for key in ("memory_hits", "event_hits", "recent_turns"):
        value = captured.get(key)
        if isinstance(value, list):
            captured[key] = [_redact_hit(item) for item in value]
    profile = captured.get("profile")
    if isinstance(profile, dict):
        captured["profile"] = dict(profile)
    return captured


def _redact_hit(item: object) -> object:
    if not isinstance(item, dict):
        return item
    redacted = dict(item)
    if "text" in redacted and "id" in redacted:
        redacted["text_len"] = len(str(redacted.pop("text")))
    return redacted
