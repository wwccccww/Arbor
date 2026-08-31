from __future__ import annotations

import json

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool

from arbor.adapters.inbound.http.schemas import MessageIn
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId


def reject_oversize(data: bytes, limit: int) -> None:
    if len(data) > limit:
        raise DomainError("VALIDATION_ERROR", "file too large")


async def read_chat_payload(
    request: Request,
    storage,
    tenant: TenantId,
    thread_id: str,
    max_upload_bytes: int,
) -> tuple[str, list]:
    content_type = request.headers.get("content-type") or ""
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text") or "")
        attachments: list[dict] = []
        uploads: list = []
        if hasattr(form, "getlist"):
            uploads.extend(form.getlist("file"))
        single = form.get("file")
        if single is not None and single not in uploads:
            uploads.append(single)
        for upload in uploads:
            if upload is None or not hasattr(upload, "read"):
                continue
            data = await upload.read()
            reject_oversize(data, max_upload_bytes)
            filename = str(getattr(upload, "filename", None) or "upload.bin")
            filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip() or "upload.bin"
            uri = storage.put(f"chat/{tenant.value}/{thread_id}/{filename}", data)
            attachments.append({"filename": filename, "uri": uri})
        return text, attachments
    try:
        body = await request.json()
    except Exception as exc:
        raise DomainError("VALIDATION_ERROR", "invalid json") from exc
    if not isinstance(body, dict):
        raise DomainError("VALIDATION_ERROR", "invalid body")
    payload = MessageIn.model_validate(body)
    return payload.text, list(payload.attachments or [])


def sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def parse_stream_finished(raw: str) -> dict:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {"text": raw}


async def sse_stream(streamer, extra_inbox_created: int = 0):
    from arbor.domain.conversation.stream import StreamFinished

    final: dict | None = None
    try:
        async for chunk in iterate_in_threadpool(streamer):
            if isinstance(chunk, StreamFinished):
                final = parse_stream_finished(chunk.raw)
                continue
            if isinstance(chunk, str) and chunk:
                yield sse_event({"type": "delta", "text": chunk})
    except DomainError as exc:
        yield sse_event(
            {
                "type": "error",
                "error": {"code": exc.code, "message": str(exc)},
            }
        )
        return
    if final is None:
        final = {"text": ""}
    yield sse_event(
        {
            "type": "done",
            "message_id": final.get("message_id"),
            "text": final.get("text", ""),
            "citations": final.get("citation_items") or [],
            "injected_memory_ids": final.get("injected_memory_ids") or [],
            "inbox_created": (final.get("inbox_added") or 0) + int(extra_inbox_created or 0),
            "attachments": final.get("attachments") or [],
            "retrieval_meta": final.get("retrieval_meta") or {},
            "decision_trace": final.get("decision_trace") or {},
            "context_truncation_notes": final.get("context_truncation_notes") or [],
            "request_id": final.get("request_id"),
            "tool_results": final.get("tool_results") or [],
        }
    )
