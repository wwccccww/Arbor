from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable


class SpanHandle(Protocol):
  def set_attribute(self, key: str, value: object) -> None: ...


@runtime_checkable
class ObservabilityPort(Protocol):
    def event(self, name: str, **fields: object) -> None: ...

    def span(self, name: str, **fields: object) -> AbstractContextManager[SpanHandle]: ...

    def increment(self, name: str, value: float = 1, **labels: str) -> None: ...

    def observe(self, name: str, value: float, **labels: str) -> None: ...

    def set_gauge(self, name: str, value: float, **labels: str) -> None: ...
