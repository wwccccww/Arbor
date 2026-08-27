from __future__ import annotations

from arbor.adapters.inbound.eval_runner import ROOT, _ports, load_world
from arbor.application.query_planner import plan_queries
from arbor.application.retrieval import retrieve
from arbor.domain.shared.ids import PersonaId, TenantId


def test_causal_query_planner_intent():
    planned = plan_queries("为什么后来一周没说话？", "rules")
    assert planned[0]["intent"] == "causal"


def test_causal_retrieval_recovers_fight_and_silence_memories():
    stores = __import__(
        "arbor.adapters.outbound.inmemory", fromlist=["InMemoryStores"]
    ).InMemoryStores()
    load_world(ROOT / "eval/fixtures/suite-v1/world.json", stores)
    memories, events, _, index, embed, summary = _ports(stores)
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    retrieved = retrieve(
        strategy="layered_tree",
        query="为什么后来一周没说话？",
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
    hit_ids = set(retrieved["hit_ids"])
    assert "0a000000-0000-4000-a000-000000000303" in hit_ids
    assert "0a000000-0000-4000-a000-000000000304" in hit_ids
