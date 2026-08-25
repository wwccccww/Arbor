import pytest

from arbor.adapters.outbound.object_storage import build_object_storage, object_store_label
from arbor.adapters.outbound.postgres.blobs import PgBlobObjectStorage


def test_build_object_storage_postgres_backend(monkeypatch):
    monkeypatch.setenv("ARBOR_OBJECT_STORE", "postgres")

    class Session:
        conn = object()

    storage = build_object_storage(session=Session())
    assert isinstance(storage, PgBlobObjectStorage)
    assert object_store_label(storage) == "postgres"


def test_build_object_storage_s3_from_env(monkeypatch):
    monkeypatch.setenv("ARBOR_OBJECT_STORE", "s3")
    monkeypatch.setenv("ARBOR_S3_BUCKET", "arbor")
    monkeypatch.setenv("ARBOR_S3_ENDPOINT", "http://127.0.0.1:9000")
    monkeypatch.setenv("ARBOR_S3_ACCESS_KEY", "arbor")
    monkeypatch.setenv("ARBOR_S3_SECRET_KEY", "secret")
    from arbor.adapters.outbound.s3 import S3ObjectStorage

    storage = build_object_storage()
    assert isinstance(storage, S3ObjectStorage)
    assert object_store_label(storage) == "s3"
