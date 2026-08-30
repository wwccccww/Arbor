from __future__ import annotations

import logging

logger = logging.getLogger("arbor.observability")


def instrument_fastapi(app: object) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        logger.debug("OpenTelemetry FastAPI instrumentation unavailable")


def instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except ImportError:
        logger.debug("OpenTelemetry httpx instrumentation unavailable")
