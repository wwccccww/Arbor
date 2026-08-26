from __future__ import annotations

from arbor.adapters.outbound.multimodal.docx_parser import parse_docx
from arbor.adapters.outbound.multimodal.pdf_pypdf import parse_pdf_pypdf
from arbor.adapters.outbound.multimodal.plain_text import parse_plain_text
from arbor.adapters.outbound.multimodal.pptx_parser import parse_pptx
from arbor.adapters.outbound.multimodal.types import MediaParseResult
from arbor.domain.shared.media_kinds import MediaKind, media_kind_for_filename


def parse_document(data: bytes, filename: str) -> MediaParseResult:
    kind = media_kind_for_filename(filename)
    lower = (filename or "").lower()
    if kind is MediaKind.TEXT:
        return parse_plain_text(data, filename)
    if lower.endswith(".pdf"):
        try:
            return parse_pdf_pypdf(data, filename)
        except Exception:
            return MediaParseResult(chunks=[], parser="pypdf", media_kind="document")
    if lower.endswith(".docx"):
        try:
            return parse_docx(data, filename)
        except Exception:
            return MediaParseResult(chunks=[], parser="python-docx", media_kind="document")
    if lower.endswith(".pptx"):
        try:
            return parse_pptx(data, filename)
        except Exception:
            return MediaParseResult(chunks=[], parser="python-pptx", media_kind="document")
    if kind is MediaKind.DOCUMENT:
        # html / legacy doc: try plain decode fallback
        return parse_plain_text(data, filename)
    return MediaParseResult(chunks=[], parser="none", media_kind=kind.value)
