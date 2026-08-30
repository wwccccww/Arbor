from __future__ import annotations

import time
from contextlib import contextmanager

from arbor.observability.helpers import obs_or_noop


@contextmanager
def observed_dependency(
    observability: object | None,
    *,
    dependency: str,
    operation: str,
    retry_count: int = 0,
):
    obs = obs_or_noop(observability)
    started = time.perf_counter()
    result = "success"
    try:
        yield
    except Exception:
        result = "error"
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        obs.event(
            "dependency.call",
            dependency=dependency,
            operation=operation,
            result=result,
            duration_ms=duration_ms,
            retry_count=retry_count,
        )


class ObservedObjectStorage:
    """Wrap object storage with dependency.call events."""

    def __init__(self, inner: object, observability: object | None) -> None:
        self._inner = inner
        self._observability = observability

    def put(self, key: str, data: bytes) -> str:
        with observed_dependency(self._observability, dependency="object_store", operation="put"):
            return self._inner.put(key, data)

    def get(self, key: str) -> bytes | None:
        with observed_dependency(self._observability, dependency="object_store", operation="get"):
            return self._inner.get(key)

    def delete(self, key: str) -> None:
        with observed_dependency(self._observability, dependency="object_store", operation="delete"):
            return self._inner.delete(key)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)
