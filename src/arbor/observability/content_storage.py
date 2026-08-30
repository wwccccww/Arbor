from __future__ import annotations

from typing import Any

from arbor.observability.content_capture import build_encrypted_content_sample
from arbor.observability.sampling import decrypt_payload


def store_encrypted_content_sample(
    *,
    storage: object | None,
    tenant_id: str,
    request_id: str,
    user_message: str,
    model_response: str,
    prompt_slots: dict[str, Any] | None,
    reasoning_content: str | None,
) -> tuple[str | None, str | None, bool]:
    """Return (legacy_inline_encrypted, object_uri, sampled)."""
    inline, sampled = build_encrypted_content_sample(
        tenant_id=tenant_id,
        user_message=user_message,
        model_response=model_response,
        prompt_slots=prompt_slots,
        reasoning_content=reasoning_content,
    )
    if not sampled or not inline:
        return None, None, False
    if storage is None or not hasattr(storage, "put"):
        return inline, None, True
    key = f"decision-traces/{tenant_id}/{request_id}.enc"
    uri = storage.put(key, inline.encode("utf-8"))
    return None, str(uri), True


def load_encrypted_content(entry: dict, storage: object | None) -> str | None:
    uri = entry.get("encrypted_payload_uri")
    if uri and storage is not None and hasattr(storage, "get"):
        blob = storage.get(str(uri))
        if blob is None:
            return None
        payload = blob.decode("utf-8") if isinstance(blob, bytes) else str(blob)
        return decrypt_payload(payload)
    inline = entry.get("encrypted_payload")
    if inline:
        return decrypt_payload(str(inline))
    return None


def delete_encrypted_content(entry: dict, storage: object | None) -> None:
    uri = entry.get("encrypted_payload_uri")
    if not uri or storage is None or not hasattr(storage, "delete"):
        return
    try:
        storage.delete(str(uri))
    except OSError:
        pass
