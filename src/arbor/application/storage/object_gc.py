from __future__ import annotations

from typing import Any


def delete_stored_object(storage: Any, uri: str | None) -> bool:
    """Delete one object key if the storage adapter supports delete."""
    if not uri or storage is None:
        return False
    delete = getattr(storage, "delete", None)
    if not callable(delete):
        return False
    return bool(delete(str(uri)))


def object_uris_from_memory_source(source: dict | None) -> list[str]:
    """Collect blob keys referenced on a MemoryItem source payload."""
    if not source:
        return []
    keys: list[str] = []
    for field in ("object_uri", "uri"):
        value = source.get(field)
        if value:
            keys.append(str(value))
    chunk_meta = source.get("chunk_meta")
    if isinstance(chunk_meta, dict):
        nested = chunk_meta.get("object_uri")
        if nested:
            keys.append(str(nested))
    return keys


def list_stored_keys(storage: Any, prefix: str = "") -> list[str]:
    """List object keys when the storage adapter implements list_keys."""
    list_keys = getattr(storage, "list_keys", None)
    if not callable(list_keys):
        return []
    keys = list_keys(prefix)
    return [str(key) for key in keys if key]


def sweep_orphan_objects(storage: Any, referenced_uris: set[str], prefix: str = "") -> list[str]:
    """Delete stored objects not referenced by memory/import/chat metadata."""
    referenced = {str(uri).replace("\\", "/").lstrip("/") for uri in referenced_uris if uri}
    deleted: list[str] = []
    for key in list_stored_keys(storage, prefix):
        normalized = str(key).replace("\\", "/").lstrip("/")
        if normalized in referenced:
            continue
        if delete_stored_object(storage, key):
            deleted.append(key)
    return deleted
