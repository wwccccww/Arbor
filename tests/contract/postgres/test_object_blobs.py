import pytest

from arbor.adapters.outbound.postgres.blobs import PgBlobObjectStorage


@pytest.mark.postgres
def test_pg_blob_roundtrip_on_real_postgres(pg_session):
    storage = PgBlobObjectStorage(pg_session.conn)
    uri = storage.put("contract/demo.bin", b"pg-bytes")
    assert storage.get(uri) == b"pg-bytes"
    assert storage.count() >= 1
