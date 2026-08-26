from __future__ import annotations

from pathlib import Path


class LocalFileObjectStorage:
    """Disk-backed object storage for uploads and chat attachments."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, name: str) -> Path:
        candidate = Path(name)
        if candidate.is_absolute() and candidate.is_file():
            return candidate
        safe = name.replace("\\", "/").lstrip("/")
        return self.root / safe

    def put(self, name: str, data: bytes) -> str:
        path = self._path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)

    def get(self, name: str) -> bytes | None:
        path = self._path_for(name)
        if not path.is_file():
            alt = self.root / name
            if alt.is_file():
                path = alt
            else:
                return None
        return path.read_bytes()

    def delete(self, name: str) -> bool:
        path = self._path_for(name)
        if not path.is_file():
            alt = self.root / name
            if alt.is_file():
                path = alt
            else:
                return False
        path.unlink(missing_ok=True)
        return True

    def count(self) -> int:
        return sum(1 for _ in self.root.rglob("*") if _.is_file())
