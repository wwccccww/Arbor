from __future__ import annotations

import base64

import pytest

from arbor.observability.content_storage import (
    delete_encrypted_content,
    load_encrypted_content,
    store_encrypted_content_sample,
)


def _enable_capture(monkeypatch) -> None:
    key = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_CONTENT", "true")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_TENANTS", "t1")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("OBSERVABILITY_ENCRYPTION_KEY", key)


class _FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> str:
        self.objects[key] = data
        return f"s3://test-bucket/{key}"

    def get(self, uri: str) -> bytes | None:
        if uri.startswith("s3://test-bucket/"):
            key = uri.replace("s3://test-bucket/", "")
        else:
            key = uri.split("/")[-1]
        return self.objects.get(key)

    def delete(self, uri: str) -> None:
        if uri.startswith("s3://test-bucket/"):
            key = uri.replace("s3://test-bucket/", "")
        else:
            key = uri.split("/")[-1]
        self.objects.pop(key, None)


@pytest.mark.integration
def test_encrypted_content_unreadable_after_delete(monkeypatch):
    _enable_capture(monkeypatch)
    storage = _FakeStorage()
    _inline, uri, sampled = store_encrypted_content_sample(
        storage=storage,
        tenant_id="t1",
        request_id="req-del-001",
        user_message="secret",
        model_response="hi",
        prompt_slots={},
        reasoning_content=None,
    )
    assert sampled
    assert uri
    storage_key = uri.replace("s3://test-bucket/", "")
    assert storage_key in storage.objects
    loaded = load_encrypted_content(
        {"encrypted_payload_uri": uri, "content_sampled": True},
        storage=storage,
    )
    assert loaded is not None
    delete_encrypted_content({"encrypted_payload_uri": uri}, storage)
    assert storage_key not in storage.objects
    assert (
        load_encrypted_content(
            {"encrypted_payload_uri": uri, "content_sampled": True},
            storage=storage,
        )
        is None
    )
