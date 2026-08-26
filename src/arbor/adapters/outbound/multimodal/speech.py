from __future__ import annotations

import io
import tempfile
from pathlib import Path

from arbor.adapters.outbound.multimodal.types import MediaChunk, MediaParseResult


class FasterWhisperTranscriber:
    def __init__(self, *, model_size: str = "base") -> None:
        self.model_size = model_size
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, data: bytes, filename: str) -> MediaParseResult:
        model = self._load()
        suffix = Path(filename or "audio.bin").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            segments, _info = model.transcribe(path)
            text = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
        finally:
            Path(path).unlink(missing_ok=True)
        if not text:
            return MediaParseResult(chunks=[], parser="faster-whisper", media_kind="audio")
        chunk = MediaChunk(
            text=text,
            memory_type="transcript",
            metadata={"source": filename, "parser": "faster-whisper"},
        )
        return MediaParseResult(chunks=[chunk], parser="faster-whisper", media_kind="audio")


class StubTranscriber:
    """Demo / tests when faster-whisper is unavailable."""

    def transcribe(self, data: bytes, filename: str) -> MediaParseResult:
        return MediaParseResult(chunks=[], parser="stub", media_kind="audio")
