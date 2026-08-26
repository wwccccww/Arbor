from __future__ import annotations

import logging
from io import BytesIO

from arbor.adapters.outbound.multimodal.chunking import chunk_text
from arbor.adapters.outbound.multimodal.types import MediaChunk, MediaParseResult
from arbor.domain.shared.media_kinds import media_kind_for_filename

logger = logging.getLogger("arbor.multimodal.docling")


def docling_available() -> bool:
    try:
        import docling  # noqa: F401

        return True
    except ImportError:
        return False


def parse_docling(data: bytes, filename: str) -> MediaParseResult:
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    name = (filename or "document").rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "document"
    converter = DocumentConverter()
    stream = DocumentStream(name=name, stream=BytesIO(data))
    result = converter.convert(stream)
    markdown = result.document.export_to_markdown()
    kind = media_kind_for_filename(filename)
    media_kind = kind.value if kind.value != "unknown" else "document"
    chunks = [
        MediaChunk(
            text=piece,
            memory_type="file_chunk",
            metadata={"source": filename, "parser": "docling"},
        )
        for piece in chunk_text(markdown)
    ]
    return MediaParseResult(chunks=chunks, parser="docling", media_kind=media_kind)
