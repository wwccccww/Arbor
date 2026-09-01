from __future__ import annotations

from pathlib import Path

from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient
from arbor.adapters.outbound.postgres.agent import (
    PgAgentRunRepository,
    PgAgentStepRepository,
    PgApprovalRepository,
    PgToolExecutionRepository,
)
from arbor.adapters.outbound.postgres.alembic_runner import upgrade_head
from arbor.adapters.outbound.postgres.artifacts import (
    PgArtifactLineageRepository,
    PgArtifactRepository,
    PgArtifactSegmentRepository,
)
from arbor.adapters.outbound.postgres.audit import PgAuditLogRepository
from arbor.adapters.outbound.postgres.connection import connect, wipe_public_schema
from arbor.adapters.outbound.postgres.connection_scope import RequestScopedConnection
from arbor.adapters.outbound.postgres.decision_traces import PgDecisionTraceRepository
from arbor.adapters.outbound.postgres.employee import PgEmployeeDefinitionRepository
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
    def __init__(self, conn, url: str, embed=None, pool=None, observability=None) -> None:
        self.conn = conn
        self.url = url
        self.embed = embed or FixtureEmbeddingClient()
        self._pool = pool
        self._observability = observability
        self._primary_conn = conn
        self._scoped = RequestScopedConnection(lambda: self._primary_conn)
        self._bind()

    def _bind(self) -> None:
        conn = self._scoped
        self.personas = PgPersonaRepository(conn)
        self.memories = PgMemoryRepository(conn)
        self.inbox = PgInboxRepository(conn)
        self.events = PgEventGraphRepository(conn)
        self.threads = PgThreadRepository(conn)
        self.vectors = PgVectorIndex(conn, self.memories)
        self.audit_logs = PgAuditLogRepository(conn)
        self.decision_traces = PgDecisionTraceRepository(conn)
        self.tenants = PgTenantRepository(conn)
        self.users = PgUserRepository(conn)
        self.agent_runs = PgAgentRunRepository(conn)
        self.agent_steps = PgAgentStepRepository(conn)
        self.approvals = PgApprovalRepository(conn)
        self.tool_executions = PgToolExecutionRepository(conn)
        self.artifacts = PgArtifactRepository(conn)
        self.artifact_segments = PgArtifactSegmentRepository(conn)
        self.artifact_lineage = PgArtifactLineageRepository(conn)
        self.employee_definitions = PgEmployeeDefinitionRepository(conn)

    def borrow_connection(self) -> tuple[object, bool]:
        if self._pool is None:
            return self._primary_conn, False
        from arbor.observability.postgres import observe_connection

        conn = observe_connection(self._pool.getconn(), self._observability)
        return conn, True

    def release_connection(self, conn: object, borrowed: bool) -> None:
        if borrowed and self._pool is not None:
            self._pool.putconn(conn)

    def checkout(self) -> tuple[object, bool]:
        """Deprecated: use borrow_connection + request-scoped routing instead."""
        return self.borrow_connection()

    def checkin(self, conn: object, borrowed: bool) -> None:
        self.release_connection(conn, borrowed)

    @classmethod
    def connect(
        cls,
        url: str,
        embed=None,
        *,
        use_pool: bool = True,
        observability=None,
    ) -> PostgresSession:
        from arbor.observability.postgres import observe_connection

        pool = None
        if use_pool:
            try:
                from arbor.adapters.outbound.postgres.pool import open_pool

                pool = open_pool(url)
                conn = observe_connection(pool.getconn(), observability)
            except Exception:
                pool = None
                conn = connect(url, observability=observability)
        else:
            conn = connect(url, observability=observability)
        return cls(conn, url, embed=embed, pool=pool, observability=observability)

    def migrate(self) -> None:
        # Close before Alembic. 0001 opens a second connection to apply
        # schema.sql; keeping this session open across that can deadlock.
        if self._pool is not None:
            self._pool.close()
            self._pool = None
        if self.conn is not None and not self.conn.closed:
            self.conn.close()
        upgrade_head(self.url)
        self.conn = connect(self.url, observability=self._observability)
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
