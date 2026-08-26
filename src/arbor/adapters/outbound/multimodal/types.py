from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MediaChunk:
    text: str
    memory_type: str  # fact | file_chunk | transcript | image_caption
    metadata: dict = field(default_factory=dict)


@dataclass
class MediaParseResult:
    chunks: list[MediaChunk]
    parser: str
    media_kind: str
