from __future__ import annotations

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


def test_memory_v1_smoke_gates():
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
    report = run_memory_smoke(
        fixture_path=ROOT / "eval" / "fixtures" / "memory-v1" / "cases.json",
        memories=memories,
        vectors=vectors,
        embed=embed,
        personas=personas,
        ids=SeqIdGenerator(start=900),
        consolidate=consolidate,
        delete=delete,
        confirm=confirm,
        inbox=inbox,
    )
    assert report["gate_pass_rate"] == 1.0
    assert report["stale_memory_injection_rate"] == 0.0
    assert report["conflict_injection_rate"] == 0.0
    assert report["memory_write_precision"] == 1.0
    assert report["memory_helpfulness_rate"] == 1.0
    assert len(report["cases"]) == 9
