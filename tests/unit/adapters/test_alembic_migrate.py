from arbor.adapters.outbound.postgres.alembic_runner import (
    CONNECT_TIMEOUT_SECONDS,
    migration_connect_args,
    sqlalchemy_url,
)
from arbor.adapters.outbound.postgres.session import PostgresSession


def test_sqlalchemy_url_uses_psycopg_driver():
    assert (
        sqlalchemy_url("postgresql://arbor:arbor@127.0.0.1:5432/arbor")
        == "postgresql+psycopg://arbor:arbor@127.0.0.1:5432/arbor"
    )


def test_migration_connect_args_fail_fast():
    args = migration_connect_args()
    assert args["connect_timeout"] == CONNECT_TIMEOUT_SECONDS
    assert "lock_timeout=15s" in str(args["options"])
    assert "statement_timeout=60s" in str(args["options"])


def test_migrate_closes_app_connection_before_upgrade(monkeypatch):
    closed: list[bool] = []

    class FakeConn:
        closed = False

        def close(self) -> None:
            self.closed = True
            closed.append(True)

    opened: list[FakeConn] = []

    def fake_connect(url: str, **kwargs):
        conn = FakeConn()
        opened.append(conn)
        return conn

    monkeypatch.setattr("arbor.adapters.outbound.postgres.session.upgrade_head", lambda url: None)
    monkeypatch.setattr("arbor.adapters.outbound.postgres.session.connect", fake_connect)

    session = PostgresSession(FakeConn(), "postgresql://arbor:arbor@127.0.0.1:5432/arbor")
    session.migrate()
    assert closed == [True]
    assert session.conn is opened[0]
    assert session.conn.closed is False
