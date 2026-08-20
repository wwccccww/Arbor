from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here.parent, *here.parents]:
        if (path / "eval" / "fixtures" / "suite-v1" / "world.json").exists():
            return path
    return Path.cwd()
