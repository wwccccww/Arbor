from __future__ import annotations

from arbor.application.storage.object_gc import (
    list_stored_keys,
    object_uris_from_memory_source,
    sweep_orphan_objects,
)


class _Storage:
    def __init__(self) -> None:
        self.keys = {"keep.bin": b"x", "orphan.bin": b"y"}
        self.deleted: list[str] = []

    def delete(self, name: str) -> bool:
        if name in self.keys:
            del self.keys[name]
            self.deleted.append(name)
            return True
        return False

    def list_keys(self, prefix: str = "") -> list[str]:
        keys = list(self.keys.keys())
        if prefix:
            keys = [key for key in keys if key.startswith(prefix)]
        return keys


def test_object_uris_from_memory_source_collects_keys():
    keys = object_uris_from_memory_source(
        {
            "object_uri": "imports/a.bin",
            "uri": "chat/b.png",
            "chunk_meta": {"object_uri": "imports/chunk.bin"},
        }
    )
    assert keys == ["imports/a.bin", "chat/b.png", "imports/chunk.bin"]


def test_delete_stored_object_noop_without_delete():
    from arbor.application.storage.object_gc import delete_stored_object

    assert delete_stored_object(object(), "x") is False


def test_delete_stored_object_calls_adapter():
    from arbor.application.storage.object_gc import delete_stored_object

    storage = _Storage()
    assert delete_stored_object(storage, "orphan.bin") is True
    assert storage.deleted == ["orphan.bin"]


def test_sweep_orphan_objects_deletes_unreferenced():
    storage = _Storage()
    deleted = sweep_orphan_objects(storage, {"keep.bin"})
    assert deleted == ["orphan.bin"]
    assert storage.keys == {"keep.bin": b"x"}


def test_list_stored_keys_without_adapter():
    assert list_stored_keys(object()) == []
