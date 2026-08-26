from __future__ import annotations

import io

from arbor.adapters.outbound.multimodal.chunking import chunk_text
from arbor.adapters.outbound.multimodal.types import MediaChunk, MediaParseResult


def parse_pdf_pypdf(data: bytes, filename: str) -> MediaParseResult:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    chunks: list[MediaChunk] = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        for piece in chunk_text(text):
            chunks.append(
                MediaChunk(
                    text=piece,
                    memory_type="file_chunk",
                    metadata={"source": filename, "page": page_no, "parser": "pypdf"},
                )
            )
    return MediaParseResult(chunks=chunks, parser="pypdf", media_kind="document")
