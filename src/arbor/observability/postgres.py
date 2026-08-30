from __future__ import annotations

from arbor.observability.dependency import observed_dependency


class ObservedPostgresConnection:
    """Wrap psycopg connection execute with dependency.call events."""

    def __init__(self, inner: object, observability: object | None) -> None:
        self._inner = inner
        self._observability = observability

    def execute(self, query: str, params=None):
        operation = _operation_name(query)
        with observed_dependency(
            self._observability,
            dependency="postgres",
            operation=operation,
        ):
            return self._inner.execute(query, params)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def observe_connection(conn: object, observability: object | None) -> object:
    if observability is None:
        return conn
    return ObservedPostgresConnection(conn, observability)


def _operation_name(query: str) -> str:
    stripped = (query or "").strip().split(None, 1)
    if not stripped:
        return "query"
    keyword = stripped[0].upper()
    if keyword in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
        return keyword.lower()
    return "query"
