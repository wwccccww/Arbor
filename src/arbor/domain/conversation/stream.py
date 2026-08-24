from __future__ import annotations

import json
import re


class StreamFinished(dict):
    """Sentinel yielded at the close of a model stream.

    Carries the raw model envelope so the application layer can extract
    ``citations`` once the whole reply has been streamed. ``isinstance`` checks
    on ``dict`` still work, but this marker is distinguishable from a regular
    text chunk by its ``raw`` attribute.
    """

    def __init__(self, raw: str) -> None:
        super().__init__(__final__=True, raw=raw)
        self.raw = raw


def chunk_text(text: str, size: int = 2):
    """Split ``text`` into small deterministic chunks, preserving surrogate
    pairs so emoji / astral characters render correctly when reassembled."""
    i = 0
    n = len(text)
    while i < n:
        j = min(i + size, n)
        while j > i and j < n and 0xDC00 <= ord(text[j]) <= 0xDFFF:
            j -= 1
        yield text[i:j]
        i = j


def parse_model_out(content: str) -> dict:
    """Parse the JSON envelope the model is instructed to emit into a
    ``{"text", "citations"}`` dict. Falls back to treating the raw output as
    plain text when the envelope is malformed."""
    blob = content.strip()
    match = re.search(r"\{.*\}", blob, flags=re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            text = str(data.get("text") or "")
            citations = [c for c in (data.get("citations") or []) if isinstance(c, str)]
            return {"text": text, "citations": citations}
        except json.JSONDecodeError:
            pass
    return {"text": blob, "citations": []}


def extract_text_delta(buffer: str) -> str:
    """Best-effort incremental extraction of the ``text`` JSON-string value from
    an in-progress model stream.

    The model is generating a JSON envelope, so we pull whatever portion of the
    ``text`` value is already on the wire. We stop at the first unescaped
    closing quote so we never swallow trailing fields like ``citations``, and we
    unescape JSON so emoji/escapes render correctly even when split across
    chunks.
    """
    match = re.search(r'"text"\s*:\s*"', buffer)
    if not match:
        return ""
    raw = buffer[match.end() :]
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\":
            if i + 1 >= len(raw):
                break
            out.append(raw[i : i + 2])
            i += 2
            continue
        if ch == '"':
            break
        out.append(ch)
        i += 1
    token = "".join(out)
    try:
        return json.loads('"' + token + '"')
    except json.JSONDecodeError:
        return token.replace("\\", "")
