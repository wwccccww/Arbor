from __future__ import annotations

import logging

from arbor.adapters.outbound.multimodal.document_parser import parse_document
from arbor.adapters.outbound.multimodal.plain_text import parse_plain_text
from arbor.adapters.outbound.multimodal.types import MediaParseResult
from arbor.domain.shared.media_kinds import MediaKind, media_kind_for_filename
from arbor.env import chat_api_key

logger = logging.getLogger("arbor.multimodal")


def build_speech_transcriber():
    try:
        from arbor.adapters.outbound.multimodal.speech import FasterWhisperTranscriber

        return FasterWhisperTranscriber()
    except Exception as exc:
        logger.info("faster-whisper unavailable: %s", exc)
        from arbor.adapters.outbound.multimodal.speech import StubTranscriber

        return StubTranscriber()


def build_vision_describer():
    if chat_api_key():
        from arbor.adapters.outbound.multimodal.vision import DeepSeekVisionDescriber

        return DeepSeekVisionDescriber()
    from arbor.adapters.outbound.multimodal.vision import StubVisionDescriber

    return StubVisionDescriber()


def parse_media_bytes(data: bytes, filename: str) -> MediaParseResult:
    kind = media_kind_for_filename(filename)
    if kind is MediaKind.AUDIO:
        transcriber = build_speech_transcriber()
        return transcriber.transcribe(data, filename)
    if kind is MediaKind.IMAGE:
        describer = build_vision_describer()
        return describer.describe(data, filename)
    if kind in {MediaKind.TEXT, MediaKind.DOCUMENT}:
        if kind is MediaKind.TEXT:
            return parse_plain_text(data, filename)
        return parse_document(data, filename)
    # unknown: try utf-8 text
    plain = parse_plain_text(data, filename)
    if plain.chunks:
        return plain
    return MediaParseResult(chunks=[], parser="none", media_kind=kind.value)
