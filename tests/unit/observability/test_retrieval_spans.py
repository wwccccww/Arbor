from __future__ import annotations

from arbor.application.retrieval import retrieve
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from arbor.observability.memory import InMemoryObservability


def _memory(mid: str, text: str) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(mid),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text=text,
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
    )


def test_retrieve_emits_rag_spans():
    obs = InMemoryObservability()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    memories = [_memory("m1", "售后手册说明"), _memory("m2", "住在杭州")]

    def vector_search(**kwargs):
        return [(memories[0], 0.9)]

    def embed(text: str):
        return [0.1, 0.2]

    retrieve(
        strategy="vector_only",
        query="手册",
        tenant_id=tenant,
        persona_id=persona,
        k=2,
        memories=memories,
        events=[],
        summary="",
        vector_search=vector_search,
        embed=embed,
        observability=obs,
    )
    span_names = [span.name for span in obs.spans]
    assert "rag.retrieve" in span_names
    assert "vector.search" in span_names
    assert "rag.rerank" in span_names
    assert any(name == "rag.retrieve" for name, _ in obs.events)
