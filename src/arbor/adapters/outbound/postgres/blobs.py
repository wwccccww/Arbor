from __future__ import annotations


class PgBlobObjectStorage:
    """Persist upload/chat bytes in Postgres object_blobs."""

    def __init__(self, conn) -> None:
        self.conn = conn

    @staticmethod
    def _key(name: str) -> str:
        return (name or "").replace("\\", "/").lstrip("/")

    def put(self, name: str, data: bytes) -> str:
        key = self._key(name)
        self.conn.execute(
            """
            INSERT INTO object_blobs (key, data)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data
            """,
            (key, data),
        )
        return key

    def get(self, name: str) -> bytes | None:
        key = self._key(name)
        row = self.conn.execute(
            "SELECT data FROM object_blobs WHERE key = %s",
            (key,),
        ).fetchone()
        if row is None:
            return None
        blob = row["data"]
        if blob is None:
            return None
        return bytes(blob)

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM object_blobs").fetchone()
        return int(row["n"] if row else 0)
