from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

from arbor.observability.port import ObservabilityPort


@dataclass
class _NoopSpan:
    def set_attribute(self, key: str, value: object) -> None:
        return None


@dataclass
class NoopObservability(ObservabilityPort):
    events: list[tuple[str, dict]] = field(default_factory=list)

    def event(self, name: str, **fields: object) -> None:
        self.events.append((name, dict(fields)))

    @contextmanager
    def span(self, name: str, **fields: object):
        yield _NoopSpan()

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        return None

    def observe(self, name: str, value: float, **labels: str) -> None:
        return None

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        return None
