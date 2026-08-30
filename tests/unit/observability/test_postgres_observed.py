from __future__ import annotations

from unittest.mock import MagicMock

from arbor.observability.memory import InMemoryObservability
from arbor.observability.postgres import ObservedPostgresConnection


def test_observed_postgres_execute_emits_dependency_call():
    inner = MagicMock()
    inner.execute.return_value = {"n": 1}
    obs = InMemoryObservability()
    conn = ObservedPostgresConnection(inner, obs)
    conn.execute("SELECT 1")
    assert any(name == "dependency.call" for name, _ in obs.events)
    event = next(fields for name, fields in obs.events if name == "dependency.call")
    assert event["dependency"] == "postgres"
    assert event["operation"] == "select"


def test_observed_postgres_skips_when_no_observability():
    inner = MagicMock()
    conn = ObservedPostgresConnection(inner, None)
    conn.execute("INSERT INTO t VALUES (1)")
    inner.execute.assert_called_once()
