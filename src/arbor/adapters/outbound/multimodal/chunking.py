from __future__ import annotations

import re

from arbor.env import chunk_max_chars, chunk_overlap_chars

_HEADING = re.compile(r"^#{1,6}\s+.+", re.MULTILINE)


def chunk_text(text: str, *, max_chars: int | None = None, overlap: int | None = None) -> list[str]:
    max_len = max_chars if max_chars is not None else chunk_max_chars()
    overlap_len = overlap if overlap is not None else chunk_overlap_chars()
    stripped = (text or "").strip()
    if not stripped:
        return []
    if len(stripped) <= max_len:
        return [stripped]
    sections: list[str] = []
    if _HEADING.search(stripped):
        parts = re.split(r"(?=^#{1,6}\s+)", stripped, flags=re.MULTILINE)
        sections = [p.strip() for p in parts if p.strip()]
    else:
        sections = [p.strip() for p in re.split(r"\n\s*\n+", stripped) if p.strip()]
    if not sections:
        sections = [stripped]
    out: list[str] = []
    buf = ""
    for section in sections:
        if len(section) > max_len:
            if buf:
                out.append(buf.strip())
                buf = ""
            start = 0
            while start < len(section):
                end = min(len(section), start + max_len)
                piece = section[start:end].strip()
                if piece:
                    out.append(piece)
                if end >= len(section):
                    break
                start = max(start + 1, end - overlap_len)
            continue
        candidate = f"{buf}\n\n{section}".strip() if buf else section
        if len(candidate) <= max_len:
            buf = candidate
        else:
            if buf:
                out.append(buf.strip())
            buf = section
    if buf:
        out.append(buf.strip())
    return [chunk for chunk in out if chunk]
