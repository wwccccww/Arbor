from __future__ import annotations

import json
from pathlib import Path

import pytest

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.application.evaluation.memory_runner import run_memory_smoke
from arbor.application.memory.commands import ConfirmInboxItem
from arbor.application.memory.consolidate_episodes import ConsolidateEpisodicMemories
from arbor.application.memory.delete_memory import DeleteMemory
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")

MEMORY_CLASSES_ROOT = ROOT / "eval" / "fixtures" / "memory-classes-v1"


def _memory_stack():
    stores = InMemoryStores()
    load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    embed = FixtureEmbeddingClient()
    persona = personas.get(TENANT, LINXIA)
    if persona is not None:
        persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))
    consolidate = ConsolidateEpisodicMemories(
        personas=personas,
        memories=memories,
        vectors=vectors,
        embed=embed,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    delete = DeleteMemory(
        personas=personas,
        memories=memories,
        vectors=vectors,
        auth=AuthorizationPolicy(),
    )
    confirm = ConfirmInboxItem(
        personas=personas,
        memories=memories,
        inbox=inbox,
        vectors=vectors,
        embed=embed,
        ids=SeqIdGenerator(start=800),
        auth=AuthorizationPolicy(),
    )
    return {
        "memories": memories,
        "vectors": vectors,
        "embed": embed,
        "personas": personas,
        "consolidate": consolidate,
        "delete": delete,
        "confirm": confirm,
        "inbox": inbox,
    }


def _class_fixture_paths() -> list[tuple[str, Path, str]]:
    manifest = json.loads((MEMORY_CLASSES_ROOT / "manifest.json").read_text(encoding="utf-8"))
    out: list[tuple[str, Path, str]] = []
    for entry in manifest.get("classes") or []:
        memory_class = str(entry.get("memory_class") or "")
        fixture_name = str(entry.get("fixture") or "")
        metric = str(entry.get("metric") or "")
        path = MEMORY_CLASSES_ROOT / fixture_name
        out.append((memory_class, path, metric))
    return out


@pytest.mark.parametrize(
    ("memory_class", "fixture_path", "metric_name"),
    _class_fixture_paths(),
)
def test_memory_class_fixture_gate(memory_class: str, fixture_path: Path, metric_name: str):
    stack = _memory_stack()
    report = run_memory_smoke(
        fixture_path=fixture_path,
        memories=stack["memories"],
        vectors=stack["vectors"],
        embed=stack["embed"],
        personas=stack["personas"],
        ids=SeqIdGenerator(start=900),
        consolidate=stack["consolidate"],
        delete=stack["delete"],
        confirm=stack["confirm"],
        inbox=stack["inbox"],
    )
    assert report["gate_pass_rate"] == 1.0
    assert report["stale_memory_injection_rate"] == 0.0
    assert report["conflict_injection_rate"] == 0.0
    for case in report.get("cases") or []:
        assert case.get("ok") is True, case
    delete_cases = [c for c in report.get("cases") or [] if "delete" in str(c.get("id"))]
    assert delete_cases, f"{memory_class} missing delete case"
    assert metric_name, f"{memory_class} metric not declared in manifest"
