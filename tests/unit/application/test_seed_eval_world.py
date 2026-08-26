from __future__ import annotations

import json
from pathlib import Path

import pytest

from arbor.adapters.inbound.eval_runner import load_world as load_inmemory_world
from arbor.adapters.outbound.inmemory import InMemoryStores
from arbor.adapters.outbound.postgres.world import clear_inmemory_tenant_scope
from arbor.application.evaluation.seed_world import SeedEvalWorld
from arbor.domain.errors import DomainError
from arbor.paths import repo_root


def _fixture_path(suite_version: str) -> Path:
    if suite_version != "v1":
        raise DomainError("VALIDATION_ERROR", f"unsupported suite {suite_version}")
    return repo_root() / "eval" / "fixtures" / "suite-v1" / "world.json"


def test_seed_eval_world_inmemory():
    stores = InMemoryStores()
    path = _fixture_path("v1")
    load_inmemory_world(path, stores)
    world = json.loads(path.read_text(encoding="utf-8"))
    persona_ids = {row["id"] for row in world["personas"]}

    seed = SeedEvalWorld(
        fixture_path_for=_fixture_path,
        pg_clear=lambda _session, _tenant_ids: None,
        pg_load=lambda _session, _path: None,
        mem_clear=clear_inmemory_tenant_scope,
        mem_load=load_inmemory_world,
    )
    result = seed(suite_version="v1", stores=stores)
    assert result["suite_version"] == "v1"
    assert all(pid in stores.personas for pid in persona_ids)


def test_seed_eval_world_rejects_unknown_suite():
    seed = SeedEvalWorld(
        fixture_path_for=_fixture_path,
        pg_clear=lambda _s, _t: None,
        pg_load=lambda _s, _p: None,
        mem_clear=lambda _s, _t: None,
        mem_load=lambda _p, _s: None,
    )
    with pytest.raises(DomainError):
        seed(suite_version="unknown", stores=InMemoryStores())
