"""Per-request Postgres connection routing for pooled API handlers."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any

_request_connection: ContextVar[Any] = ContextVar("arbor_pg_request_connection", default=None)


class RequestScopedConnection:
    """Repository-facing proxy that uses the active request connection when set."""

    def __init__(self, fallback: Callable[[], Any]) -> None:
        self._fallback = fallback

    def _active(self) -> Any:
        scoped = _request_connection.get()
        if scoped is not None:
            return scoped
        return self._fallback()

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self._active().execute(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._active(), name)


def set_request_connection(conn: Any) -> Token[Any]:
    return _request_connection.set(conn)


def reset_request_connection(token: Token[Any]) -> None:
    _request_connection.reset(token)
