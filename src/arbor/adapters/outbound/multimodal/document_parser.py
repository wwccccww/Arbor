from __future__ import annotations

import logging

from arbor.adapters.outbound.multimodal.docx_parser import parse_docx
from arbor.adapters.outbound.multimodal.libreoffice_convert import convert_legacy_to_modern, is_legacy_office_filename
from arbor.adapters.outbound.multimodal.pdf_pypdf import parse_pdf_pypdf
from arbor.adapters.outbound.multimodal.plain_text import parse_plain_text
from arbor.adapters.outbound.multimodal.pptx_parser import parse_pptx
from arbor.adapters.outbound.multimodal.types import MediaParseResult
from arbor.domain.shared.media_kinds import MediaKind, media_kind_for_filename
from arbor.env import document_parser_backend

logger = logging.getLogger("arbor.multimodal.document")


def parse_document(data: bytes, filename: str) -> MediaParseResult:
    work_data = data
    work_name = filename
    if is_legacy_office_filename(filename):
        converted = convert_legacy_to_modern(data, filename)
        if converted:
            work_data, work_name = converted
            logger.info("legacy office converted %s -> %s", filename, work_name)

    backend = document_parser_backend()
    if backend in {"docling", "auto"}:
        try:
            from arbor.adapters.outbound.multimodal.docling_parser import docling_available, parse_docling

            if docling_available():
                docling_result = parse_docling(work_data, work_name)
                if docling_result.chunks or backend == "docling":
                    return docling_result
        except Exception as exc:
            logger.warning("docling parse failed for %s: %s", work_name, exc)
            if backend == "docling":
                return MediaParseResult(chunks=[], parser="docling", media_kind="document")

    return _parse_light(work_data, work_name)


def _parse_light(data: bytes, filename: str) -> MediaParseResult:
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
        return parse_plain_text(data, filename)
    return MediaParseResult(chunks=[], parser="none", media_kind=kind.value)
