from __future__ import annotations

import json
from pathlib import Path

from arbor.adapters.inbound.eval_runner import ROOT, _ports, load_world
from arbor.application.retrieval import retrieve
from arbor.domain.shared.ids import PersonaId, TenantId

RAGAS_DIR = ROOT / "eval" / "fixtures" / "suite-ragas-official"


def _load_ragas_ports():
    stores = __import__(
        "arbor.adapters.outbound.inmemory", fromlist=["InMemoryStores"]
    ).InMemoryStores()
    world_path = RAGAS_DIR / "knowledge_graph.json"
    load_world(world_path, stores)
    return _ports(stores)


def _case(case_id: str) -> dict:
    cases = json.loads((RAGAS_DIR / "cases.json").read_text(encoding="utf-8"))
    return next(case for case in cases if case["id"] == case_id)


def test_profile_residence_query_injects_expected_memory():
    memories, events, _, index, embed, summary = _load_ragas_ports()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    case = _case("ragas-llm-002")
    retrieved = retrieve(
        strategy="layered_tree",
        query=case["query"],
        tenant_id=tenant,
        persona_id=persona,
        k=5,
        memories=memories.list_active(tenant, persona),
        events=events.list_nodes(tenant, persona),
        edges=events.list_edges(tenant, persona),
        summary=summary(persona),
        vector_search=index.search,
        embed=embed.embed,
    )
    injected = {memory.id.value for memory in retrieved["hits"]}
    assert case["expected_memory_ids"][0] in injected
    assert case["expected_memory_ids"][0] in retrieved["injected_hit_ids"]


def test_profile_taboo_query_keeps_vector_hits():
    memories, events, _, index, embed, summary = _load_ragas_ports()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    case = _case("ragas-llm-004")
    retrieved = retrieve(
        strategy="layered_tree",
        query=case["query"],
        tenant_id=tenant,
        persona_id=persona,
        k=5,
        memories=memories.list_active(tenant, persona),
        events=events.list_nodes(tenant, persona),
        edges=events.list_edges(tenant, persona),
        summary=summary(persona),
        vector_search=index.search,
        embed=embed.embed,
    )
    assert retrieved["vector_hits"]
    assert len(retrieved["hits"]) > 0


def test_multihop_episode_query_includes_photo_memory():
    memories, events, _, index, embed, summary = _load_ragas_ports()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    case = _case("ragas-llm-052")
    retrieved = retrieve(
        strategy="layered_tree",
        query=case["query"],
        tenant_id=tenant,
        persona_id=persona,
        k=5,
        memories=memories.list_active(tenant, persona),
        events=events.list_nodes(tenant, persona),
        edges=events.list_edges(tenant, persona),
        summary=summary(persona),
        vector_search=index.search,
        embed=embed.embed,
    )
    injected = {memory.id.value for memory in retrieved["hits"]}
    assert all(mid in injected for mid in case["expected_memory_ids"])
