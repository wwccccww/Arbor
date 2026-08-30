from __future__ import annotations

from typing import TYPE_CHECKING

from arbor.observability.noop import NoopObservability

if TYPE_CHECKING:
    from arbor.observability.port import ObservabilityPort


def obs_or_noop(obs: object | None) -> ObservabilityPort:
    if obs is None:
        return NoopObservability()
    return obs  # type: ignore[return-value]


def size_bucket(num_bytes: int) -> str:
    size = max(0, int(num_bytes))
    if size < 1024:
        return "lt_1k"
    if size < 32 * 1024:
        return "lt_32k"
    if size < 256 * 1024:
        return "lt_256k"
    return "gte_256k"


def http_status_class(status_code: int) -> str:
    if status_code < 200:
        return "1xx"
    if status_code < 300:
        return "2xx"
    if status_code < 400:
        return "3xx"
    if status_code < 500:
        return "4xx"
    return "5xx"
