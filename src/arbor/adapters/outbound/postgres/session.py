from __future__ import annotations

from pathlib import Path

from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient
from arbor.adapters.outbound.postgres.connection import connect, reset_schema
from arbor.adapters.outbound.postgres.events import PgEventGraphRepository
from arbor.adapters.outbound.postgres.inbox import PgInboxRepository
from arbor.adapters.outbound.postgres.memory import PgMemoryRepository
from arbor.adapters.outbound.postgres.persona import PgPersonaRepository
from arbor.adapters.outbound.postgres.thread import PgThreadRepository
from arbor.adapters.outbound.postgres.vector import PgVectorIndex
from arbor.adapters.outbound.postgres.world import load_mini_world, load_world


class PostgresSession:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.personas = PgPersonaRepository(conn)
        self.memories = PgMemoryRepository(conn)
        self.inbox = PgInboxRepository(conn)
        self.events = PgEventGraphRepository(conn)
        self.threads = PgThreadRepository(conn)
        self.vectors = PgVectorIndex(conn, self.memories)
        self.embed = FixtureEmbeddingClient()

    @classmethod
    def connect(cls, url: str) -> PostgresSession:
        return cls(connect(url))

    def reset(self) -> None:
        reset_schema(self.conn)
        self.personas = PgPersonaRepository(self.conn)
        self.memories = PgMemoryRepository(self.conn)
        self.inbox = PgInboxRepository(self.conn)
        self.events = PgEventGraphRepository(self.conn)
        self.threads = PgThreadRepository(self.conn)
        self.vectors = PgVectorIndex(self.conn, self.memories)

    def load_world(self, path: Path) -> None:
        load_world(self, path)

    def load_mini_world(self) -> None:
        load_mini_world(self)

    def close(self) -> None:
        self.conn.close()
