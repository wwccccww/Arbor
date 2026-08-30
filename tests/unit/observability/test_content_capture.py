from __future__ import annotations

import base64
import importlib.util

import pytest

from arbor.observability.content_capture import build_encrypted_content_sample
from arbor.observability.sampling import decrypt_payload


@pytest.mark.skipif(importlib.util.find_spec("cryptography") is None, reason="cryptography not installed")
def test_content_capture_encrypts_when_enabled(monkeypatch):
    key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_CONTENT", "true")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_SAMPLE_RATE", "1")
    monkeypatch.setenv("OBSERVABILITY_ENCRYPTION_KEY", key)
    encrypted, sampled = build_encrypted_content_sample(
        tenant_id="tenant-a",
        user_message="用户问题",
        model_response="模型回答",
        prompt_slots={"profile": {"display_name": "测试"}},
        reasoning_content="hidden chain",
    )
    assert sampled is True
    assert encrypted
    decoded = decrypt_payload(encrypted)
    assert decoded is not None
    assert decoded["user_message"] == "用户问题"
    assert decoded["reasoning_content"] == "hidden chain"
