from __future__ import annotations

from arbor.application.storage.object_gc import delete_stored_object, object_uris_from_memory_source


class _Storage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, name: str) -> bool:
        self.deleted.append(name)
        return True


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
    assert delete_stored_object(object(), "x") is False


def test_delete_stored_object_calls_adapter():
    storage = _Storage()
    assert delete_stored_object(storage, "imports/job/1.txt") is True
    assert storage.deleted == ["imports/job/1.txt"]
