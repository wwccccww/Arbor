from __future__ import annotations

from fastapi.responses import JSONResponse

from arbor.observability.context import current_request_context
from arbor.observability.request_id import new_request_id


def error_response(code: str, message: str, status: int, request_id: str | None = None) -> JSONResponse:
    ctx = current_request_context()
    resolved = request_id or (ctx.request_id if ctx is not None else new_request_id())
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": resolved}},
        headers={"X-Request-Id": resolved},
    )
