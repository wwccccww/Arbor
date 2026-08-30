from __future__ import annotations

import time
from contextlib import contextmanager

from arbor.observability.helpers import http_status_class, obs_or_noop


@contextmanager
def observed_llm_call(
    observability: object | None,
    *,
    operation: str,
    model: str,
    stream: str = "false",
):
    obs = obs_or_noop(observability)
    started = time.perf_counter()
    status_code = 200
    try:
        yield
    except Exception as exc:
        status_code = getattr(exc, "status_code", 500)
        obs.increment(
            "arbor_llm_requests_total",
            operation=operation,
            model=model,
            result="error",
        )
        obs.increment(
            "arbor_llm_upstream_errors_total",
            operation=operation,
            status_class=http_status_class(int(status_code)),
        )
        raise
    finally:
        duration = time.perf_counter() - started
        obs.observe(
            "arbor_llm_duration_seconds",
            duration,
            operation=operation,
            model=model,
        )
        if status_code < 400:
            obs.event(
                f"llm.{operation}",
                model=model,
                stream=stream,
                duration_ms=round(duration * 1000, 2),
                result="success",
            )


def record_llm_usage(
    observability: object | None,
    *,
    operation: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    first_token_ms: float | None = None,
) -> None:
    obs = obs_or_noop(observability)
    if input_tokens is not None:
        obs.increment(
            "arbor_llm_input_tokens_total",
            float(input_tokens),
            operation=operation,
            model=model,
        )
    if output_tokens is not None:
        obs.increment(
            "arbor_llm_output_tokens_total",
            float(output_tokens),
            operation=operation,
            model=model,
        )
    if first_token_ms is not None:
        obs.observe(
            "arbor_llm_first_token_duration_seconds",
            first_token_ms / 1000.0,
            model=model,
        )
