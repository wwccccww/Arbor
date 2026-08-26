from __future__ import annotations

import io

from arbor.adapters.outbound.multimodal.chunking import chunk_text
from arbor.adapters.outbound.multimodal.types import MediaChunk, MediaParseResult


def parse_docx(data: bytes, filename: str) -> MediaParseResult:
    from docx import Document

    doc = Document(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    text = "\n\n".join(paragraphs)
    chunks = [
        MediaChunk(
            text=piece,
            memory_type="file_chunk",
            metadata={"source": filename, "parser": "python-docx"},
        )
        for piece in chunk_text(text)
    ]
    return MediaParseResult(chunks=chunks, parser="python-docx", media_kind="document")
