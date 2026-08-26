from __future__ import annotations

from arbor.domain.conversation.thread import Thread

SUMMARY_MIN_MESSAGES = 4
SUMMARY_MAX_LINES = 16
SUMMARY_MAX_CHARS = 400


def compress_thread_summary(thread: Thread, reasoner) -> str | None:
    """Roll recent dialogue into a short thread summary for retrieval context."""
    if len(thread.messages) < SUMMARY_MIN_MESSAGES:
        return None
    lines: list[str] = []
    for msg in thread.messages[-SUMMARY_MAX_LINES:]:
        role = (msg.role or "user").strip()
        content = (msg.content or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    if not lines:
        return None
    blob = "\n".join(lines)
    summarize = getattr(reasoner, "summarize", None)
    if summarize is None:
        return _truncate(blob.replace("\n", " "))
    summary = summarize(blob, prior=thread.summary or "")
    if not summary:
        return None
    return _truncate(summary)


def _truncate(text: str) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= SUMMARY_MAX_CHARS:
        return stripped
    return stripped[: SUMMARY_MAX_CHARS - 1].rstrip() + "…"
