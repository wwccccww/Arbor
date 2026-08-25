from __future__ import annotations

import tempfile
from pathlib import Path

from arbor.adapters.outbound.inmemory import InMemoryObjectStorage, InMemoryStores
from arbor.adapters.outbound.localfs import LocalFileObjectStorage
from arbor.adapters.outbound.postgres.blobs import PgBlobObjectStorage
from arbor.adapters.outbound.s3 import S3ObjectStorage
from arbor.env import data_dir, object_store_backend


def build_object_storage(
    *,
    session=None,
    stores: InMemoryStores | None = None,
) -> object:
    """Pick object storage backend from env and runtime mode.

    ARBOR_OBJECT_STORE:
      - local (default): files under ARBOR_DATA_DIR/objects
      - postgres: bytea in object_blobs (requires DATABASE_URL session)
      - s3: S3-compatible bucket (MinIO / AWS)
    """
    backend = object_store_backend()
    if backend == "s3":
        return S3ObjectStorage.from_env()
    if backend == "postgres":
        if session is None:
            raise RuntimeError("ARBOR_OBJECT_STORE=postgres requires DATABASE_URL")
        return PgBlobObjectStorage(session.conn)
    root = data_dir() / "objects"
    if session is None:
        root = Path(tempfile.mkdtemp(prefix="arbor-objects-"))
    storage = LocalFileObjectStorage(root)
    if stores is not None and stores.objects:
        mem_storage = InMemoryObjectStorage(stores)
        for key in list(stores.objects.keys()):
            blob = mem_storage.get(key)
            if blob is not None:
                storage.put(key, blob)
    return storage


def object_store_label(storage: object) -> str:
    if isinstance(storage, S3ObjectStorage):
        return "s3"
    if isinstance(storage, PgBlobObjectStorage):
        return "postgres"
    if isinstance(storage, LocalFileObjectStorage):
        return "local"
    return "memory"
