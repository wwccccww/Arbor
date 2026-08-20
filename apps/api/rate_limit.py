from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from arbor.domain.errors import DomainError

DEFAULT_RATE_LIMIT_PER_WINDOW = 120
DEFAULT_RATE_WINDOW_SECONDS = 60


class InMemoryRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> None:
        now = self._clock()
        cutoff = now - self.window_seconds
        q = self._hits.get(key)
        if q is None:
            q = deque()
            self._hits[key] = q
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.limit:
            raise DomainError("RATE_LIMITED", "rate limited")
        q.append(now)
