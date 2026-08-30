from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from arbor.observability.json_log import JsonEventLogger
from arbor.observability.port import ObservabilityPort


@dataclass
class _ProductionSpan:
    otel_span: Any | None

    def set_attribute(self, key: str, value: object) -> None:
        if self.otel_span is not None:
            self.otel_span.set_attribute(key, value)


@dataclass
class ProductionObservability(ObservabilityPort):
    logger: JsonEventLogger
    metrics: object
    tracer: Any | None = None
    events: list[tuple[str, dict]] = field(default_factory=list)

    def event(self, name: str, **fields: object) -> None:
        self.events.append((name, dict(fields)))
        self.logger.emit(name, **fields)

    @contextmanager
    def span(self, name: str, **fields: object):
        started = time.perf_counter()
        otel_span = None
        if self.tracer is not None:
            otel_span = self.tracer.start_span(name)
        handle = _ProductionSpan(otel_span)
        for key, value in fields.items():
            if value is not None:
                handle.set_attribute(key, value)
        try:
            yield handle
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if otel_span is not None:
                otel_span.set_attribute("duration_ms", duration_ms)
                otel_span.end()
            self.event(f"{name}.completed", duration_ms=duration_ms, **fields)

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        self.metrics.increment(name, value, **labels)

    def observe(self, name: str, value: float, **labels: str) -> None:
        self.metrics.observe(name, value, **labels)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        self.metrics.set_gauge(name, value, **labels)
