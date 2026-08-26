from __future__ import annotations

import re

_HEADING = re.compile(r"^#{1,6}\s+.+", re.MULTILINE)


def chunk_text(text: str, *, max_chars: int = 1200) -> list[str]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    if len(stripped) <= max_chars:
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
        if len(section) > max_chars:
            if buf:
                out.append(buf.strip())
                buf = ""
            start = 0
            while start < len(section):
                out.append(section[start : start + max_chars].strip())
                start += max_chars
            continue
        candidate = f"{buf}\n\n{section}".strip() if buf else section
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                out.append(buf.strip())
            buf = section
    if buf:
        out.append(buf.strip())
    return [c for c in out if c]
