from __future__ import annotations

import hashlib
import re
from contextvars import ContextVar
from dataclasses import dataclass

from arbor.observability.request_id import new_request_id

_REQUEST_CTX: ContextVar[RequestContext | None] = ContextVar("arbor_request_context", default=None)

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str | None = None
    tenant_id: str | None = None
    persona_id: str | None = None
    thread_id: str | None = None
    actor_id: str | None = None


def normalize_request_id(raw: str | None) -> str:
    candidate = (raw or "").strip()
    if _ULID_RE.fullmatch(candidate):
        return candidate
    return new_request_id()


def tenant_id_hash(tenant_id: str | None) -> str | None:
    if not tenant_id:
        return None
    digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def current_request_context() -> RequestContext | None:
    return _REQUEST_CTX.get()


def set_request_context(ctx: RequestContext) -> object:
    return _REQUEST_CTX.set(ctx)


def reset_request_context(token: object) -> None:
    _REQUEST_CTX.reset(token)


def merge_request_context(**updates: object) -> RequestContext:
    current = current_request_context()
    base = current or RequestContext(request_id=new_request_id())
    return RequestContext(
        request_id=str(updates.get("request_id") or base.request_id),
        trace_id=updates.get("trace_id") if "trace_id" in updates else base.trace_id,
        tenant_id=updates.get("tenant_id") if "tenant_id" in updates else base.tenant_id,
        persona_id=updates.get("persona_id") if "persona_id" in updates else base.persona_id,
        thread_id=updates.get("thread_id") if "thread_id" in updates else base.thread_id,
        actor_id=updates.get("actor_id") if "actor_id" in updates else base.actor_id,
    )
