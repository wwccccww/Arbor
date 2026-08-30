from __future__ import annotations

import base64

from arbor.observability.sampling import (
    decrypt_payload,
    encrypt_payload,
    should_capture_content,
)


def test_should_capture_respects_tenant_allowlist(monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_CONTENT", "true")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_SAMPLE_RATE", "1")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_TENANTS", "tenant-a")
    assert should_capture_content(tenant_id="tenant-a") is True
    assert should_capture_content(tenant_id="tenant-b") is False


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("OBSERVABILITY_ENCRYPTION_KEY", key.decode("ascii"))
    token = encrypt_payload({"user_message": "hello", "model_response": "hi"})
    assert token
    decoded = decrypt_payload(token)
    assert decoded == {"user_message": "hello", "model_response": "hi"}


def test_encrypt_missing_key_returns_none(monkeypatch):
    monkeypatch.delenv("OBSERVABILITY_ENCRYPTION_KEY", raising=False)
    assert encrypt_payload({"x": 1}) is None
