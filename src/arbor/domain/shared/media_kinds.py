from __future__ import annotations

from enum import Enum


class MediaKind(str, Enum):
    TEXT = "text"
    DOCUMENT = "document"
    AUDIO = "audio"
    IMAGE = "image"
    UNKNOWN = "unknown"


_TEXT = {".md", ".markdown", ".txt", ".text", ".csv", ".json"}
_DOCUMENT = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".html",
    ".htm",
    ".rtf",
}
_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


def media_kind_for_filename(filename: str) -> MediaKind:
    lower = (filename or "").lower().rsplit("/", 1)[-1]
    if "." not in lower:
        return MediaKind.UNKNOWN
    ext = "." + lower.rsplit(".", 1)[-1]
    if ext in _TEXT:
        return MediaKind.TEXT
    if ext in _DOCUMENT:
        return MediaKind.DOCUMENT
    if ext in _AUDIO:
        return MediaKind.AUDIO
    if ext in _IMAGE:
        return MediaKind.IMAGE
    return MediaKind.UNKNOWN
