from arbor.adapters.outbound.postgres.blobs import PgBlobObjectStorage


class FakeConn:
    def __init__(self) -> None:
        self.rows: dict[str, bytes] = {}

    def execute(self, sql, params=()):
        sql_norm = " ".join(sql.split())
        if sql_norm.startswith("INSERT INTO object_blobs"):
            key, data = params
            self.rows[key] = bytes(data)
            return _Row(None)
        if sql_norm.startswith("SELECT data FROM object_blobs"):
            key = params[0]
            if key not in self.rows:
                return _Row(None)
            return _Row({"data": self.rows[key]})
        if sql_norm.startswith("SELECT COUNT(*) AS n FROM object_blobs"):
            return _Row({"n": len(self.rows)})
        raise AssertionError(sql_norm)


class _Row:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


def test_pg_blob_put_get_roundtrip():
    storage = PgBlobObjectStorage(FakeConn())
    uri = storage.put("imports/demo.txt", b"hello")
    assert uri == "imports/demo.txt"
    assert storage.get(uri) == b"hello"
    assert storage.count() == 1
