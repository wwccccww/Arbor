from __future__ import annotations

import os
import time

from fastapi.responses import JSONResponse

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_request_id() -> str:
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")
    n = (ms << 80) | rand
    chars = ["0"] * 26
    for i in range(25, -1, -1):
        chars[i] = _CROCKFORD[n & 31]
        n >>= 5
    return "".join(chars)


def error_response(code: str, message: str, status: int, request_id: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id or new_request_id()}},
    )
