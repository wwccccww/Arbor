from __future__ import annotations

from contextlib import contextmanager

from arbor.observability.dependency import observed_dependency


@contextmanager
def observed_redis(observability: object | None, operation: str):
    with observed_dependency(observability, dependency="redis", operation=operation):
        yield
