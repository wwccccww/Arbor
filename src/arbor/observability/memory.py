from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from arbor.observability.port import ObservabilityPort, SpanHandle


@dataclass
class RecordedSpan:
    name: str
    fields: dict
    started_at: float
    ended_at: float | None = None
    attributes: dict = field(default_factory=dict)


@dataclass
class InMemorySpan:
    recorder: InMemoryObservability
    span: RecordedSpan

    def set_attribute(self, key: str, value: object) -> None:
        self.span.attributes[key] = value


@dataclass
class InMemoryObservability(ObservabilityPort):
    events: list[tuple[str, dict]] = field(default_factory=list)
    spans: list[RecordedSpan] = field(default_factory=list)
    counters: list[tuple[str, float, dict]] = field(default_factory=list)
    observations: list[tuple[str, float, dict]] = field(default_factory=list)
    gauges: list[tuple[str, float, dict]] = field(default_factory=list)

    def event(self, name: str, **fields: object) -> None:
        self.events.append((name, dict(fields)))

    @contextmanager
    def span(self, name: str, **fields: object):
        span = RecordedSpan(name=name, fields=dict(fields), started_at=time.perf_counter())
        self.spans.append(span)
        handle: SpanHandle = InMemorySpan(self, span)
        try:
            yield handle
        finally:
            span.ended_at = time.perf_counter()

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        self.counters.append((name, value, dict(labels)))

    def observe(self, name: str, value: float, **labels: str) -> None:
        self.observations.append((name, value, dict(labels)))

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        self.gauges.append((name, value, dict(labels)))
