from __future__ import annotations

from arbor.adapters.outbound.multimodal.chunking import chunk_text
from arbor.adapters.outbound.multimodal.types import MediaChunk, MediaParseResult


def parse_plain_text(data: bytes, filename: str) -> MediaParseResult:
    try:
        text = data.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        text = ""
    chunks = [
        MediaChunk(text=piece, memory_type="file_chunk", metadata={"source": filename})
        for piece in chunk_text(text)
    ]
    return MediaParseResult(chunks=chunks, parser="plain_text", media_kind="text")
