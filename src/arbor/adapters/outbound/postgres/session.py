from __future__ import annotations

from pathlib import Path

from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient
from arbor.adapters.outbound.postgres.alembic_runner import upgrade_head
from arbor.adapters.outbound.postgres.audit import PgAuditLogRepository
from arbor.adapters.outbound.postgres.connection import connect, wipe_public_schema
from arbor.adapters.outbound.postgres.decision_traces import PgDecisionTraceRepository
from arbor.adapters.outbound.postgres.events import PgEventGraphRepository
from arbor.adapters.outbound.postgres.identity import PgTenantRepository, PgUserRepository
from arbor.adapters.outbound.postgres.inbox import PgInboxRepository
from arbor.adapters.outbound.postgres.memory import PgMemoryRepository
from arbor.adapters.outbound.postgres.persona import PgPersonaRepository
from arbor.adapters.outbound.postgres.thread import PgThreadRepository
from arbor.adapters.outbound.postgres.vector import PgVectorIndex
from arbor.adapters.outbound.postgres.world import load_mini_world, load_world
from arbor.paths import repo_root


class PostgresSession:
    def __init__(self, conn, url: str, embed=None, pool=None) -> None:
        self.conn = conn
        self.url = url
        self.embed = embed or FixtureEmbeddingClient()
        self._pool = pool
        self._primary_conn = conn
        self._bind()

    def _bind(self, conn=None) -> None:
        conn = conn or self.conn
        self.conn = conn
        self.personas = PgPersonaRepository(self.conn)
        self.memories = PgMemoryRepository(self.conn)
        self.inbox = PgInboxRepository(self.conn)
        self.events = PgEventGraphRepository(self.conn)
        self.threads = PgThreadRepository(self.conn)
        self.vectors = PgVectorIndex(self.conn, self.memories)
        self.audit_logs = PgAuditLogRepository(self.conn)
        self.decision_traces = PgDecisionTraceRepository(self.conn)
        self.tenants = PgTenantRepository(self.conn)
        self.users = PgUserRepository(self.conn)

    def checkout(self) -> tuple[object, bool]:
        if self._pool is None:
            return self.conn, False
        conn = self._pool.getconn()
        self._bind(conn)
        return conn, True

    def checkin(self, conn: object, borrowed: bool) -> None:
        if borrowed and self._pool is not None:
            self._pool.putconn(conn)
            self._bind(self._primary_conn)

    @classmethod
    def connect(cls, url: str, embed=None, *, use_pool: bool = True) -> PostgresSession:
        pool = None
        if use_pool:
            try:
                from arbor.adapters.outbound.postgres.pool import open_pool

                pool = open_pool(url)
                conn = pool.getconn()
            except Exception:
                pool = None
                conn = connect(url)
        else:
            conn = connect(url)
        return cls(conn, url, embed=embed, pool=pool)

    def migrate(self) -> None:
        # Close before Alembic. 0001 opens a second connection to apply
        # schema.sql; keeping this session open across that can deadlock.
        if self._pool is not None:
            self._pool.close()
            self._pool = None
        if self.conn is not None and not self.conn.closed:
            self.conn.close()
        upgrade_head(self.url)
        self.conn = connect(self.url)
        self._primary_conn = self.conn
        self._bind()

    def reset(self) -> None:
        wipe_public_schema(self.conn)
        self.migrate()

    def is_empty(self) -> bool:
        found = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'tenants'
            """
        ).fetchone()
        if not found or int(found["n"]) == 0:
            return True
        row = self.conn.execute("SELECT COUNT(*) AS n FROM tenants").fetchone()
        return int(row["n"] if row else 0) == 0

    def seed_demo_world_if_empty(self) -> bool:
        if not self.is_empty():
            return False
        self.load_world(repo_root() / "eval" / "fixtures" / "suite-v1" / "world.json")
        return True

    def load_world(self, path: Path) -> None:
        load_world(self, path)

    def load_mini_world(self) -> None:
        load_mini_world(self)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
        elif self.conn is not None and not self.conn.closed:
            self.conn.close()
