from __future__ import annotations

from pathlib import Path
from typing import Callable

from arbor.domain.errors import DomainError


class SeedEvalWorld:
    """Reload a frozen eval world fixture. Wiring is injected from the composition root."""

    def __init__(
        self,
        *,
        fixture_path_for: Callable[[str], Path],
        pg_clear: Callable,
        pg_load: Callable,
        mem_clear: Callable,
        mem_load: Callable,
    ) -> None:
        self._fixture_path_for = fixture_path_for
        self._pg_clear = pg_clear
        self._pg_load = pg_load
        self._mem_clear = mem_clear
        self._mem_load = mem_load

    def __call__(
        self,
        *,
        suite_version: str = "v1",
        session=None,
        stores=None,
    ) -> dict:
        path = self._fixture_path_for(suite_version)
        if not path.is_file():
            raise DomainError("NOT_FOUND", "world fixture missing")
        import json

        world = json.loads(path.read_text(encoding="utf-8"))
        tenant_ids = [str(row["id"]) for row in world.get("tenants") or []]
        if session is not None:
            self._pg_clear(session, tenant_ids)
            self._pg_load(session, path)
        elif stores is not None:
            self._mem_clear(stores, tenant_ids)
            self._mem_load(path, stores)
        else:
            raise DomainError("VALIDATION_ERROR", "no persistence backend")
        return {
            "suite_version": suite_version,
            "tenant_ids": tenant_ids,
            "persona_count": len(world.get("personas") or []),
            "memory_count": len(world.get("memories") or []),
        }
