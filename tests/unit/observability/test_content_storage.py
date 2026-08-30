from __future__ import annotations

import base64
from unittest.mock import MagicMock

from arbor.observability.content_storage import (
    delete_encrypted_content,
    load_encrypted_content,
    store_encrypted_content_sample,
)
from arbor.observability.sampling import encrypt_payload


def _enable_capture(monkeypatch, tenant_id: str = "tenant-a") -> None:
    key = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_CONTENT", "true")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_TENANTS", tenant_id)
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("OBSERVABILITY_ENCRYPTION_KEY", key)


def test_store_encrypted_content_sample_uses_object_storage(monkeypatch):
    _enable_capture(monkeypatch)
    storage = MagicMock()
    storage.put.return_value = "decision-traces/tenant-a/r1.enc"
    inline, uri, sampled = store_encrypted_content_sample(
        storage=storage,
        tenant_id="tenant-a",
        request_id="r1",
        user_message="hello",
        model_response="world",
        prompt_slots={},
        reasoning_content=None,
    )
    assert sampled is True
    assert inline is None
    assert uri == "decision-traces/tenant-a/r1.enc"
    storage.put.assert_called_once()


def test_load_encrypted_content_from_uri(monkeypatch):
    _enable_capture(monkeypatch)
    payload = encrypt_payload({"user_message": "hi"})
    assert payload is not None
    storage = MagicMock()
    storage.get.return_value = payload.encode("utf-8")
    content = load_encrypted_content(
        {"encrypted_payload_uri": "decision-traces/t/r.enc", "content_sampled": True},
        storage,
    )
    assert content is not None
    assert content["user_message"] == "hi"


def test_delete_encrypted_content():
    storage = MagicMock()
    delete_encrypted_content({"encrypted_payload_uri": "key.enc"}, storage)
    storage.delete.assert_called_once_with("key.enc")
